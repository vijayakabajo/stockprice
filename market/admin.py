from django.contrib import admin

from market.models import Stock


@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = ["ticker", "name", "primary_exchange", "asset_type", "active", "last_synced_at"]
    list_filter = ["active", "market", "asset_type", "primary_exchange"]
    search_fields = ["ticker", "name", "cik", "composite_figi"]
    ordering = ["ticker"]
    readonly_fields = ["created_at", "updated_at", "last_synced_at"]

    # The tables are provider-owned: a sync task will overwrite anything typed
    # here on its next run. Read-only avoids edits that quietly disappear.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


# DailyPrice and IntradayBar are deliberately not registered. They use a
# composite primary key, which the admin does not support, and a row-by-row
# admin over millions of price bars is not a thing anyone wants.
