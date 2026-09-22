def get_rest_framework_config():
    """Returns REST_FRAMEWORK settings dict."""
    return {
        "DEFAULT_AUTHENTICATION_CLASSES": [
            "rest_framework_simplejwt.authentication.JWTAuthentication",
        ],
        "DEFAULT_PERMISSION_CLASSES": [
            "rest_framework.permissions.IsAuthenticated",
        ],
        "DEFAULT_RENDERER_CLASSES": [
            "rest_framework.renderers.JSONRenderer",
        ],
        "DEFAULT_PAGINATION_CLASS": "core.pagination.StandardResultsPagination",
        "PAGE_SIZE": 20,
        "EXCEPTION_HANDLER": "core.exceptions.custom_exception_handler",
    }
