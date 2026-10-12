from django.contrib import admin

from market.models import Exchange, Sector, Stock


@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = [
        "ticker",
        "display_name",
        "primary_exchange",
        "security_type",
        "size_bucket",
        "active",
        "last_synced_at",
    ]
    list_filter = ["active", "security_type", "size_bucket", "primary_exchange", "market"]
    search_fields = ["ticker", "name", "display_name", "cik", "composite_figi"]
    ordering = ["ticker"]
    readonly_fields = ["created_at", "updated_at", "last_synced_at"]

    # The tables are provider-owned: a sync task will overwrite anything typed
    # here on its next run. Read-only avoids edits that quietly disappear.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Exchange)
class ExchangeAdmin(admin.ModelAdmin):
    list_display = ["mic", "display_name", "slug", "name", "exchange_type", "last_synced_at"]
    list_filter = ["exchange_type"]
    search_fields = ["mic", "name", "display_name", "acronym"]
    # display_name and slug are ours; everything else is overwritten by sync_exchanges.
    readonly_fields = [
        "mic",
        "operating_mic",
        "name",
        "acronym",
        "exchange_type",
        "url",
        "provider_id",
        "last_synced_at",
        "created_at",
        "updated_at",
    ]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Sector)
class SectorAdmin(admin.ModelAdmin):
    list_display = ["sic_code", "name", "slug", "has_primer"]
    search_fields = ["sic_code", "name", "sic_description"]
    # name, slug and primer are editorial; refresh_sectors only touches sic_description.
    readonly_fields = ["sic_code", "sic_description", "created_at", "updated_at"]

    @admin.display(boolean=True, description="Primer")
    def has_primer(self, obj):
        return bool(obj.primer)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


# DailyPrice and IntradayBar are deliberately not registered. They use a
# composite primary key, which the admin does not support, and a row-by-row
# admin over millions of price bars is not a thing anyone wants.
