"""Custom list filters — the theia_ng equivalent of
``django.contrib.admin.SimpleListFilter``.

Put a ``ListFilter`` subclass in a ModelAdmin's ``list_filter`` (alongside plain
field-name strings). It contributes a labelled choice dropdown to the list
filter UI and applies arbitrary queryset logic for the selected value::

    class HasAssignmentFilter(theia_ng.ListFilter):
        title = "Has assignment"
        parameter_name = "has_assignment"

        def lookups(self, request):
            return [("yes", "Has assignment"), ("no", "No assignment")]

        def queryset(self, request, queryset, value):
            if value == "yes":
                return queryset.filter(assignment_count__gt=0)
            if value == "no":
                return queryset.filter(assignment_count=0)
            return queryset
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from django.db.models import QuerySet
    from django.http import HttpRequest


class ListFilter:
    title: str = ""
    parameter_name: str = ""

    def lookups(self, request: HttpRequest | None) -> list[tuple[Any, Any]]:
        """Return ``[(value, label), ...]`` — the choices shown in the filter UI."""
        return []

    def queryset(self, request: HttpRequest, queryset: QuerySet, value: str) -> QuerySet:
        """Return the queryset filtered for the selected ``value``."""
        return queryset
