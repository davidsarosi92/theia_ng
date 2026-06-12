"""Theia NG registrations for the sample app (autodiscovered)."""

import theia_ng

from .models import Category, House, Space, Stock


@theia_ng.register(Stock)
class StockAdmin(theia_ng.ModelAdmin):
    list_display = ["name", "category", "quantity", "is_active"]
    list_filter = ["category", "is_active"]
    search_fields = ["name"]
    ordering = ["name"]
    actions = ["deactivate"]
    # Only show Spaces that belong to the Stock's currently-selected house.
    relation_filters = {"spaces": {"house": "house"}}
    # Leaf of the House → Space/Stock hierarchy (default reverse accessor: stock_set).
    tree_parent = "house"

    def deactivate(self, request, queryset):
        return {"updated": queryset.update(is_active=False)}


@theia_ng.register(House)
class HouseAdmin(theia_ng.ModelAdmin):
    list_display = ["name"]
    search_fields = ["name"]
    # Root of the hierarchy: Houses own Spaces (related_name="spaces") and Stocks.
    tree_children = ["spaces", "stock_set"]


@theia_ng.register(Space)
class SpaceAdmin(theia_ng.ModelAdmin):
    list_display = ["name", "house"]
    search_fields = ["name"]
    tree_parent = "house"


@theia_ng.register(Category)
class CategoryAdmin(theia_ng.ModelAdmin):
    list_display = ["name"]
    search_fields = ["name"]
    display_field = "name"  # label relations by this field instead of __str__
