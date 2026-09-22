import logging

from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Wraps DRF's default exception handling so every error response — validation
    errors, auth failures, 404s, throttling, unhandled exceptions — comes back
    in the same {"success": false, "message": ..., "errors": ...} shape as
    core.response.api_response() uses for success responses.
    """
    response = drf_exception_handler(exc, context)

    if response is None:
        # Unhandled exception — DRF didn't recognise it, so it would otherwise
        # bubble up into a raw 500. Log it with full context and return a
        # generic envelope instead of leaking internals to the client.
        logger.exception("Unhandled exception in %s", context.get("view"))
        return None

    message = "Request failed"
    errors = response.data
    if isinstance(response.data, dict) and "detail" in response.data:
        message = str(response.data["detail"])
        errors = {k: v for k, v in response.data.items() if k != "detail"} or None

    response.data = {"success": False, "message": message, "data": None, "errors": errors}
    return response
