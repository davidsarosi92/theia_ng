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

    def deactivate(self, request, queryset):
        return {"updated": queryset.update(is_active=False)}


@theia_ng.register(House)
class HouseAdmin(theia_ng.ModelAdmin):
    list_display = ["name"]
    search_fields = ["name"]


@theia_ng.register(Space)
class SpaceAdmin(theia_ng.ModelAdmin):
    list_display = ["name", "house"]
    search_fields = ["name"]


@theia_ng.register(Category)
class CategoryAdmin(theia_ng.ModelAdmin):
    list_display = ["name"]
    search_fields = ["name"]
