from django.contrib import admin
from django.urls import include, path

from core.views import service_landing

urlpatterns = [
    path("", service_landing, name="service-landing"),
    path("admin/", admin.site.urls),
    path("api/", include("core.urls")),
    path("api/v1/auth/", include("accounts.urls")),
]
