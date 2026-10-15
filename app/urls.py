from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("core.urls")),
    path("api/v1/", include("market.urls")),
    # The public site last: it owns the root.
    path("", include("web.urls")),
]
