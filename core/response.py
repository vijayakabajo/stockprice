from rest_framework.response import Response


def api_response(data=None, message="", success=True, status_code=200, errors=None):
    """
    Standard response envelope used across every endpoint in this project:

        {"success": bool, "message": str, "data": ..., "errors": ...}

    Keeping one shape for both success and error responses means API
    consumers never have to guess where a field lives.
    """
    payload = {"success": success, "message": message, "data": data}
    if errors is not None:
        payload["errors"] = errors
    return Response(payload, status=status_code)
