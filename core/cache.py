"""
Response caching keyed by a data version.

Every successful sync calls bump_data_version(). Cached responses carry the
version in their key, so one bump retires every cached page at once and
nothing else needs invalidating. The version is a timestamp rather than a
counter: if Redis loses the key, a fresh value can never collide with an old
one and resurrect stale entries.
"""

import hashlib
import json
import time
from functools import wraps

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse, HttpResponseNotModified
from rest_framework.response import Response
from rest_framework.views import APIView

from core.response import api_response

DATA_VERSION_KEY = "data-version"

# Safety net only: entries normally die by version bump, not by age.
RESPONSE_CACHE_TIMEOUT = 24 * 3600

# How long a browser or CDN may reuse a response without asking again.
HTTP_MAX_AGE = 300


def data_version() -> str:
    version = cache.get(DATA_VERSION_KEY)
    if version is None:
        cache.add(DATA_VERSION_KEY, str(time.time_ns()), timeout=None)
        version = cache.get(DATA_VERSION_KEY)
    return version


def bump_data_version() -> None:
    cache.set(DATA_VERSION_KEY, str(time.time_ns()), timeout=None)


class CachedAPIView(APIView):
    """
    A read-only view whose successful responses are cached per data version.

    Subclasses implement build(request, **kwargs) and return the `data` part
    of the envelope. Errors are raised as exceptions (Http404,
    ValidationError) and are never cached. Responses carry an ETag, and a
    request whose If-None-Match matches gets an empty 304.
    """

    http_method_names = ["get", "head", "options"]

    def build(self, request, **kwargs):
        raise NotImplementedError

    def get(self, request, **kwargs):
        key = self._cache_key(request)
        hit = cache.get(key)
        if hit is None:
            data = self.build(request, **kwargs)
            body = json.dumps(data, sort_keys=True, default=str)
            hit = (data, hashlib.sha256(body.encode()).hexdigest()[:32])
            cache.set(key, hit, timeout=RESPONSE_CACHE_TIMEOUT)

        data, digest = hit
        etag = f'"{digest}"'
        if etag in request.headers.get("If-None-Match", ""):
            response = Response(status=304)
        else:
            response = api_response(data=data)
        response["ETag"] = etag
        response["Cache-Control"] = f"public, max-age={HTTP_MAX_AGE}"
        return response

    @staticmethod
    def _cache_key(request):
        query = "&".join(f"{k}={v}" for k, v in sorted(request.query_params.items()))
        raw = f"{request.path}?{query}"
        return f"api:{data_version()}:{hashlib.sha256(raw.encode()).hexdigest()}"


def cache_html(params=()):
    """
    Caches a server-rendered page per data version, like CachedAPIView does
    for JSON.

    The key also carries settings.RELEASE, because a page changes on deploy
    too (templates, hashed static file names) and not only on a sync. Only
    the query parameters named in `params` are part of the key: anything else
    (utm tags, cache busters) cannot multiply cache entries, and the view
    must not read it. Only 200s are cached; redirects and 404s are rendered
    every time. Off in DEBUG, so template edits show immediately.
    """

    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if settings.DEBUG or request.method not in ("GET", "HEAD"):
                return view(request, *args, **kwargs)

            query = "&".join(f"{k}={request.GET.get(k)}" for k in sorted(params) if k in request.GET)
            raw = f"{request.path}?{query}"
            key = f"html:{data_version()}:{settings.RELEASE}:{hashlib.sha256(raw.encode()).hexdigest()}"

            hit = cache.get(key)
            if hit is None:
                response = view(request, *args, **kwargs)
                if response.status_code != 200 or response.streaming:
                    return response
                if hasattr(response, "render"):
                    response.render()
                hit = {
                    "content": response.content,
                    "content_type": response["Content-Type"],
                    "etag": hashlib.sha256(response.content).hexdigest()[:32],
                }
                cache.set(key, hit, timeout=RESPONSE_CACHE_TIMEOUT)

            etag = f'"{hit["etag"]}"'
            # GZipMiddleware weakens the ETag to W/"...", which browsers send back.
            if etag in request.headers.get("If-None-Match", ""):
                response = HttpResponseNotModified()
            else:
                response = HttpResponse(hit["content"], content_type=hit["content_type"])
            response["ETag"] = etag
            response["Cache-Control"] = f"public, max-age={HTTP_MAX_AGE}"
            return response

        return wrapper

    return decorator
