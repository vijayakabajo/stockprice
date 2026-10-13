from django.urls import path

from market import views

# <str:ticker> accepts dots: BRK.A and BF.B are real tickers.
urlpatterns = [
    path("overview/", views.OverviewView.as_view(), name="overview"),
    path("stocks/", views.StockListView.as_view(), name="stock-list"),
    path("stocks/<str:ticker>/", views.StockDetailView.as_view(), name="stock-detail"),
    path("stocks/<str:ticker>/peers/", views.StockPeersView.as_view(), name="stock-peers"),
    path("sectors/", views.SectorListView.as_view(), name="sector-list"),
    path("sectors/<slug:slug>/", views.SectorDetailView.as_view(), name="sector-detail"),
    path("exchanges/", views.ExchangeListView.as_view(), name="exchange-list"),
    path("exchanges/<slug:slug>/", views.ExchangeDetailView.as_view(), name="exchange-detail"),
    path("search/", views.SearchView.as_view(), name="search"),
    path("sitemap/", views.SitemapView.as_view(), name="sitemap"),
]
