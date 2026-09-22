import os
from urllib.parse import unquote

from django.conf import settings
from django.core.cache import cache
from django.db import connections
from django.db.utils import OperationalError
from django.http import FileResponse, HttpResponse, JsonResponse
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

import core.gcp.google_cloud as gcs_helper


def service_landing(request):
    """Root endpoint — quick sanity check that the service is up."""
    return JsonResponse(
        {
            "service": settings.PROJECT_NAME,
            "env": settings.ENV_TYPE,
            "status": "ok",
        }
    )


def health_check(request):
    """
    Liveness/readiness probe for load balancers, Docker healthchecks, etc.
    Checks the default DB connection and the cache (Redis) backend.
    """
    checks = {"database": "ok", "cache": "ok"}
    healthy = True

    try:
        connections["default"].cursor()
    except OperationalError:
        checks["database"] = "unreachable"
        healthy = False

    try:
        cache.set("health_check", "ok", timeout=5)
        if cache.get("health_check") != "ok":
            raise ValueError("cache readback mismatch")
    except Exception:
        checks["cache"] = "unreachable"
        healthy = False

    return JsonResponse(
        {"status": "ok" if healthy else "unhealthy", "checks": checks}, status=200 if healthy else 503
    )


class GetImageFromGCPView(APIView):
    """Serves a GCS-backed image, cached in Redis, with a default fallback."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        default_file = os.path.join(settings.CONTENT_DIR, "images/noimage.png")

        image_file = request.GET.get("file")
        if not image_file:
            return FileResponse(open(default_file, "rb"), content_type="image/png")

        image_file = unquote(image_file)
        cache_key = f"gcp_image::{image_file}"

        try:
            cached_image = cache.get(cache_key)
            if cached_image:
                mime_type = gcs_helper.get_mime_type_with_mimetypes(image_file)
                response = HttpResponse(cached_image, content_type=mime_type)
                response["Content-Disposition"] = f'inline; filename="{os.path.basename(image_file)}"'
                response["Cache-Control"] = "max-age=86400"
                return response

            img_blob = gcs_helper.readBlob(image_file)
            image_data = img_blob.download_as_bytes()
            cache.set(cache_key, image_data, timeout=86400)

            mime_type = gcs_helper.get_mime_type_with_mimetypes(image_file)
            response = HttpResponse(image_data, content_type=mime_type)
            response["Content-Disposition"] = f'inline; filename="{os.path.basename(image_file)}"'
            response["Cache-Control"] = "max-age=86400"
            return response

        except Exception:
            return FileResponse(open(default_file, "rb"), content_type="image/png")
