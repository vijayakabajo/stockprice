from django.conf import settings
from django.urls import path

from web import sitemaps, views

app_name = "web"

# <str:ticker> accepts dots: /stocks/brk.b/ is a real page.
urlpatterns = [
    path("", views.home, name="home"),
    path("stocks/", views.directory, name="directory"),
    path("stocks/<str:ticker>/", views.stock, name="stock"),
    path("sectors/", views.sector_index, name="sectors"),
    path("sectors/<slug:slug>/", views.sector_hub, name="sector"),
    path("exchanges/", views.exchange_index, name="exchanges"),
    path("exchanges/<slug:slug>/", views.exchange_hub, name="exchange"),
    path("search/", views.search, name="search"),
    path("guides/", views.guide_index, name="guides"),
    path("guides/<slug:slug>/", views.guide, name="guide"),
    path("glossary/", views.glossary, name="glossary"),
    path("about/", views.about, name="about"),
    path("robots.txt", views.robots_txt, name="robots"),
    path("llms.txt", views.llms_txt, name="llms"),
    path("sitemap.xml", sitemaps.sitemap_index, name="sitemap-index"),
    path("sitemap-<section>.xml", sitemaps.sitemap_section, name="sitemap-section"),
]

if settings.INDEXNOW_KEY:
    urlpatterns.append(path(f"{settings.INDEXNOW_KEY}.txt", views.indexnow_key, name="indexnow-key"))
