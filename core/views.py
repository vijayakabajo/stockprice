from django.conf import settings
from django.core.cache import cache
from django.db import connections
from django.db.utils import OperationalError
from django.http import JsonResponse


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
    Liveness/readiness probe for load balancers and uptime checks.
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
