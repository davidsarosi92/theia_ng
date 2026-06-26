"""Theia NG registrations for the sample app (autodiscovered)."""

import theia_ng

from .models import Category, House, Space, Stock


@theia_ng.register(Stock)
class StockAdmin(theia_ng.ModelAdmin):
    list_display = ["name", "category", "house__name", "quantity", "is_active"]
    list_filter = ["category", "is_active", "house__name", "created_at"]
    list_editable = ["quantity", "is_active"]
    search_fields = ["name"]
    ordering = ["name"]
    fieldsets = [
        (None, {"fields": ["name", "category", "quantity"]}),
        ("Details", {
            "fields": ["status", "is_active", "notes"],
            "classes": ["collapse"],
            "description": "Optional details.",
        }),
    ]
    actions = ["deactivate", "bulk_add", "archive", "rename_to"]
    # Only show Spaces that belong to the Stock's currently-selected house.
    relation_filters = {"spaces": {"house": "house"}}
    # Leaf of the House → Space/Stock hierarchy (default reverse accessor: stock_set).
    tree_parent = "house"

    def deactivate(self, request, queryset):
        return {"updated": queryset.update(is_active=False)}

    # Object action (detail page), dangerous, no params.
    @theia_ng.action(label="Archive", detail=True, dangerous=True)
    def archive(self, request, queryset, params):
        return {"archived": queryset.update(is_active=False)}

    # Object action with a parameter beyond the record itself.
    @theia_ng.action(
        label="Rename to",
        detail=True,
        fields=[theia_ng.ActionField("name", "string", label="New name", required=True)],
    )
    def rename_to(self, request, queryset, params):
        return {"renamed": queryset.update(name=params["name"])}

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
    list_display = ["name", "space_names"]
    search_fields = ["name"]
    # Prefetch the reverse relation walked by the computed column, to avoid N+1.
    list_prefetch_related = ["spaces"]
    # Root of the hierarchy: Houses own Spaces (related_name="spaces") and Stocks.
    tree_children = ["spaces", "stock_set"]

    @theia_ng.display(description="Spaces")
    def space_names(self, obj):
        return ", ".join(s.name for s in obj.spaces.all())

    # A placeable compact-tree field: the House's own subtree (descendants).
    @theia_ng.compact_tree(description="Structure")
    def structure(self, obj):
        return obj


@theia_ng.register(Space)
class SpaceAdmin(theia_ng.ModelAdmin):
    list_display = ["name", "house"]
    search_fields = ["name"]
    tree_parent = "house"


class StockInline(theia_ng.Inline):
    """Edit a Category's Stocks inline on the Category form."""

    model = Stock
    fk_name = "category"
    fields = ["name", "quantity", "status", "is_active"]
    extra = 1


@theia_ng.register(Category)
class CategoryAdmin(theia_ng.ModelAdmin):
    list_display = ["name"]
    search_fields = ["name"]
    display_field = "name"  # label relations by this field instead of __str__
    inlines = [StockInline]
