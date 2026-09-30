from django.urls import path, include
from rest_framework.routers import DefaultRouter
from market.views import StockViewSet

router = DefaultRouter()
router.register(r'stocks', StockViewSet, basename='stock')

urlpatterns = [
    path('', include(router.urls)),
]
