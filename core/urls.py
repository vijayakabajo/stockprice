from django.urls import path

from core.views import GetImageFromGCPView, health_check

urlpatterns = [
    path("health/", health_check, name="health-check"),
    path("image/", GetImageFromGCPView.as_view(), name="get-image"),
]
