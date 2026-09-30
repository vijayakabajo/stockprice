from rest_framework import viewsets
from rest_framework.permissions import AllowAny
from market.models import Stock
from market.serializers import StockSerializer

class StockViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only viewset for Stock reference data.
    Provides /api/stocks/ and /api/stocks/<ticker>/
    """
    queryset = Stock.objects.all().order_by("ticker")
    serializer_class = StockSerializer
    permission_classes = [AllowAny]
    lookup_field = "ticker"
