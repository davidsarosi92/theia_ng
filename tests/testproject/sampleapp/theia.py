"""Theia NG registrations for the sample app (autodiscovered)."""

import theia_ng

from .models import Category, House, Space, Stock


@theia_ng.register(Stock)
class StockAdmin(theia_ng.ModelAdmin):
    list_display = ["name", "category", "house__name", "quantity", "is_active"]
    list_filter = ["category", "is_active", "house__name", "created_at"]
    search_fields = ["name"]
    ordering = ["name"]
    actions = ["deactivate", "bulk_add"]
    # Only show Spaces that belong to the Stock's currently-selected house.
    relation_filters = {"spaces": {"house": "house"}}
    # Leaf of the House → Space/Stock hierarchy (default reverse accessor: stock_set).
    tree_parent = "house"

    def deactivate(self, request, queryset):
        return {"updated": queryset.update(is_active=False)}

    # Parameterized, selection-less action: collects a small form and creates a
    # Stock from it (exercises string + fk relation + decimal + boolean fields).
    @theia_ng.action(
        label="Bulk add stock",
        selection="none",
        fields=[
            theia_ng.ActionField("name", "string", label="Name", required=True),
            theia_ng.ActionField("category", "fk", label="Category", relation="sampleapp.category", required=True),
            theia_ng.ActionField("quantity", "decimal", label="Quantity", default="0"),
            theia_ng.ActionField("activate", "boolean", label="Active", default=True),
        ],
    )
    def bulk_add(self, request, queryset, params):
        obj = Stock.objects.create(
            name=params["name"],
            category_id=params["category"],
            quantity=params.get("quantity") or 0,
            is_active=bool(params.get("activate")),
        )
        return {"created": obj.pk}


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
