"""A django admin registration used to test admin discovery.

``Bundle`` is intentionally NOT registered with theia (see theia.py), and this
admin mixes compatible options (fields, filters, search) with incompatible ones
(a method column, a SimpleListFilter, an action) so the discovery test can prove
only the compatible subset is translated.
"""

from django.contrib import admin

from .models import Bundle


class HasStocksFilter(admin.SimpleListFilter):
    title = "Has stocks"
    parameter_name = "has_stocks"

    def lookups(self, request, model_admin):
        return [("1", "Yes"), ("0", "No")]

    def queryset(self, request, queryset):
        return queryset


@admin.register(Bundle)
class BundleAdmin(admin.ModelAdmin):
    list_display = ("name", "stock_count", "id")   # stock_count (method) -> dropped
    list_filter = ("name", HasStocksFilter)         # filter class -> dropped
    search_fields = ["name"]
    readonly_fields = ("id", "computed")            # computed (method) -> dropped
    raw_id_fields = ("stocks",)
    ordering = ["name"]
    actions = ["noop"]                              # actions -> dropped

    @admin.display(description="Stocks")
    def stock_count(self, obj):
        return obj.stocks.count()

    def computed(self, obj):
        return "x"

    @admin.action(description="No-op")
    def noop(self, request, queryset):
        pass
