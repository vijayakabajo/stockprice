from django.apps import AppConfig


class WebConfig(AppConfig):
    """The public, server-rendered site."""

    name = "web"
    default_auto_field = "django.db.models.BigAutoField"
