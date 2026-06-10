"""The ModelAdmin-equivalent configuration class.

This intentionally mirrors the *ergonomics* of ``django.contrib.admin.ModelAdmin``
so the API feels familiar — but it is our own class and does NOT import or depend
on ``django.contrib.admin``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django.db.models import Model
    from django.http import HttpRequest


class ModelAdmin:
    """Per-model admin configuration.

    Subclass and override the class attributes, then register::

        @theia_ng.register(Stock)
        class StockAdmin(theia_ng.ModelAdmin):
            list_display = ["name", "category", "quantity"]
            list_filter = ["category", "is_active"]
            search_fields = ["name"]
    """

    # --- list view ---------------------------------------------------------
    list_display: list[str] = []          # real fields + read-only properties (v1)
    list_filter: list[str] = []
    search_fields: list[str] = []
    ordering: list[str] = []
    list_per_page: int = 50

    # --- form view ---------------------------------------------------------
    fields: list[str] | None = None       # None -> all editable fields
    readonly_fields: list[str] = []

    # --- custom actions (server-side) -------------------------------------
    actions: list[str] = []

    # --- optional adapters (delegation / enrichment) ----------------------
    # If set, data ops defer to this DRF serializer (validation/save/IR flags).
    serializer_class: type | None = None
    # If set, IR fields are enriched from this OpenAPI document + component.
    openapi_schema: dict | None = None
    openapi_component: str | None = None

    def __init__(self, model: type[Model], site) -> None:
        self.model = model
        self.site = site

    # --- permission hooks (override to plug in custom auth, e.g. iBar) -----
    # Defaults delegate to django.contrib.auth model permissions. They are the
    # single integration seam for host projects with bespoke auth schemes.
    def has_view_permission(self, request: HttpRequest) -> bool:
        return self._has_perm(request, "view")

    def has_add_permission(self, request: HttpRequest) -> bool:
        return self._has_perm(request, "add")

    def has_change_permission(self, request: HttpRequest) -> bool:
        return self._has_perm(request, "change")

    def has_delete_permission(self, request: HttpRequest) -> bool:
        return self._has_perm(request, "delete")

    def _has_perm(self, request: HttpRequest, action: str) -> bool:
        opts = self.model._meta
        codename = f"{opts.app_label}.{action}_{opts.model_name}"
        user = getattr(request, "user", None)
        return bool(user and user.is_active and user.has_perm(codename))
