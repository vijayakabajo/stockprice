def get_rest_framework_config():
    """
    Returns REST_FRAMEWORK settings dict.

    The API is public and read-only: no authentication, no accounts. Views
    paginate and cache themselves (market.views), so there is no default
    pagination class.
    """
    return {
        "DEFAULT_AUTHENTICATION_CLASSES": [],
        "DEFAULT_PERMISSION_CLASSES": [
            "rest_framework.permissions.AllowAny",
        ],
        "DEFAULT_RENDERER_CLASSES": [
            "rest_framework.renderers.JSONRenderer",
        ],
        "UNAUTHENTICATED_USER": None,
        "EXCEPTION_HANDLER": "core.exceptions.custom_exception_handler",
    }
