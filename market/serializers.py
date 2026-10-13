"""
Stock serializers for the page API.

Exchange and sector come from a Labels instance passed in the serializer
context (see market.lookups). Empty provider strings become null: "missing"
has one representation, and the frontend decides how to show it.
Market cap, shares and employees are JSON numbers; they are display figures,
not money we compute with.
"""

from rest_framework import serializers

from market.classification import title_case
from market.models import Stock
from market.universe import stock_is_indexable

EDGAR_URL = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}"


class StockRowSerializer(serializers.ModelSerializer):
    """One line in a table: the directory, a hub, peers."""

    exchange = serializers.SerializerMethodField()
    sector = serializers.SerializerMethodField()
    hq = serializers.SerializerMethodField()
    market_cap = serializers.FloatField()
    indexable = serializers.SerializerMethodField()

    class Meta:
        model = Stock
        fields = [
            "ticker",
            "display_name",
            "name",
            "security_type",
            "exchange",
            "sector",
            "hq",
            "total_employees",
            "market_cap",
            "size_bucket",
            "indexable",
        ]

    def get_exchange(self, stock):
        return self.context["labels"].exchange(stock.primary_exchange)

    def get_sector(self, stock):
        return self.context["labels"].sector(stock.sic_code)

    def get_hq(self, stock):
        if not stock.city:
            return None
        city = title_case(stock.city)
        return f"{city}, {stock.state}" if stock.state else city

    def get_indexable(self, stock):
        return stock_is_indexable(stock)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        return {key: (None if value == "" else value) for key, value in data.items()}


class StockProfileSerializer(StockRowSerializer):
    """Everything the profile page shows from reference data."""

    website = serializers.CharField(source="homepage_url")
    phone = serializers.CharField(source="phone_number")
    address = serializers.SerializerMethodField()
    country = serializers.SerializerMethodField()
    currency = serializers.SerializerMethodField()
    shares_outstanding = serializers.SerializerMethodField()
    cap_per_employee = serializers.SerializerMethodField()
    edgar_url = serializers.SerializerMethodField()
    as_of = serializers.SerializerMethodField()

    class Meta(StockRowSerializer.Meta):
        fields = StockRowSerializer.Meta.fields + [
            "description",
            "website",
            "phone",
            "address",
            "country",
            "currency",
            "cik",
            "composite_figi",
            "share_class_figi",
            "sic_code",
            "ticker_root",
            "round_lot",
            "shares_outstanding",
            "cap_per_employee",
            "list_date",
            "active",
            "edgar_url",
            "as_of",
        ]

    def get_address(self, stock):
        if not (stock.address1 or stock.city):
            return None
        return {
            "line1": title_case(stock.address1) or None,
            "city": title_case(stock.city) or None,
            "state": stock.state or None,
            "postal_code": stock.postal_code or None,
        }

    def get_country(self, stock):
        return (stock.locale or "us").upper()

    def get_currency(self, stock):
        return (stock.currency_name or "usd").upper()

    def get_shares_outstanding(self, stock):
        # Class shares when the provider has them; the weighted figure covers
        # all classes over the reporting period and is the fallback.
        if stock.share_class_shares_outstanding:
            return {"value": stock.share_class_shares_outstanding, "basis": "class"}
        if stock.weighted_shares_outstanding:
            return {"value": stock.weighted_shares_outstanding, "basis": "weighted"}
        return None

    def get_cap_per_employee(self, stock):
        if stock.market_cap and stock.total_employees:
            return round(float(stock.market_cap) / stock.total_employees, 2)
        return None

    def get_edgar_url(self, stock):
        return EDGAR_URL.format(cik=stock.cik) if stock.cik else None

    def get_as_of(self, stock):
        # The profile is as fresh as its last fetch from the provider.
        synced = stock.details_synced_at or stock.last_synced_at
        return synced.isoformat() if synced else None
