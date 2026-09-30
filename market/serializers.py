from rest_framework import serializers
from market.models import Stock

class StockSerializer(serializers.ModelSerializer):
    class Meta:
        model = Stock
        fields = [
            "ticker",
            "name",
            "market",
            "locale",
            "primary_exchange",
            "asset_type",
            "currency_name",
            "active",
            "description",
            "homepage_url",
            "market_cap",
            "total_employees",
            "list_date",
        ]
