"""The ModelAdmin-equivalent configuration class.

This intentionally mirrors the *ergonomics* of ``django.contrib.admin.ModelAdmin``
so the API feels familiar — but it is our own class and does NOT import or depend
on ``django.contrib.admin``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from django.db.models import Model, QuerySet
    from django.http import HttpRequest


def display(*, description: str) -> Callable:
    """Mark a ModelAdmin method as a computed ``list_display`` column and set its
    header label (mirrors ``django.contrib.admin.display``)::

        @theia_ng.display(description="Full name")
        def full_name(self, obj):
            return f"{obj.first} {obj.last}"
    """

    def decorator(func: Callable) -> Callable:
        func.short_description = description  # type: ignore[attr-defined]
        return func

    return decorator


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
    # Shown in the form but not editable (e.g. audit fields like created_by).
    readonly_fields: list[str] = []
    # Excluded from the form entirely (still available for list_display).
    exclude: list[str] = []
    # FK/M2M rendered as a plain id input instead of a searchable picker.
    raw_id_fields: list[str] = []
    # Fields (typically JSON) whose choices are the registered model keys,
    # rendered as a multiselect. Used by MenuView to pick sidebar models.
    registry_choice_fields: list[str] = []
    # Fields rendered as a per-model field picker (grouped checkboxes), keyed by
    # the sibling field that holds the selected model keys. Used by MenuView to
    # pick which fields each included model shows. {field: models_source_field}.
    model_field_select: dict[str, str] = {}

    # --- relation label ----------------------------------------------------
    # How an instance is labelled when shown as a relation option or in an M2M
    # table. By default we use ``str(obj)`` (the model's ``__str__``). Set
    # ``display_field`` to render one concrete field instead, or override
    # ``display()`` for a fully custom label string.
    display_field: str | None = None

    # --- custom actions (server-side) -------------------------------------
    actions: list[str] = []

    # --- dependent relation options --------------------------------------
    # Limit a relation field's options by sibling field values of the record
    # being edited. Maps relation field name -> {target_lookup: source_field}.
    # e.g. {"spaces": {"house": "house"}} loads only Spaces whose house equals
    # the form's current `house` value. The filter lookups are server-defined
    # (the client only supplies the sibling values), so this is safe.
    relation_filters: dict[str, dict[str, str]] = {}

    # --- optional adapters (delegation / enrichment) ----------------------
    # If set, data ops defer to this DRF serializer (validation/save/IR flags).
    serializer_class: type | None = None
    # If set, IR fields are enriched from this OpenAPI document + component.
    openapi_schema: dict | None = None
    openapi_component: str | None = None

    def __init__(self, model: type[Model], site) -> None:
        self.model = model
        self.site = site

    # --- queryset ----------------------------------------------------------
    def get_queryset(self, request: HttpRequest) -> QuerySet:
        """Base queryset for list + detail. Override to scope rows to the user
        (e.g. by tenant) or to annotate/optimize."""
        return self.model._default_manager.all()

    # --- relation label ----------------------------------------------------
    def display(self, obj: Model) -> str:
        """Human label for an instance (relation options / M2M table).

        Defaults to ``str(obj)``. Override for a custom display string, or set
        ``display_field`` to use one concrete field's value.
        """
        if self.display_field:
            return str(getattr(obj, self.display_field, "") or "")
        return str(obj)

    # --- permission hooks (override to plug in custom auth, e.g. iBar) -----
    # Defaults delegate to django.contrib.auth model permissions. They are the
    # single integration seam for host projects with bespoke auth schemes.
    # ``obj`` is the target instance on detail endpoints (object-level checks);
    # it is None for model-level checks (list, add, the registry IR perms).
    def has_view_permission(self, request: HttpRequest, obj: Model | None = None) -> bool:
        return self._has_perm(request, "view")

    def has_add_permission(self, request: HttpRequest, obj: Model | None = None) -> bool:
        return self._has_perm(request, "add")

    def has_change_permission(self, request: HttpRequest, obj: Model | None = None) -> bool:
        return self._has_perm(request, "change")

    def has_delete_permission(self, request: HttpRequest, obj: Model | None = None) -> bool:
        return self._has_perm(request, "delete")

    def _has_perm(self, request: HttpRequest, action: str) -> bool:
        opts = self.model._meta
        codename = f"{opts.app_label}.{action}_{opts.model_name}"
        user = getattr(request, "user", None)
        return bool(user and user.is_active and user.has_perm(codename))
