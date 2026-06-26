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


class Inline:
    """Configuration for editing a parent's related child rows on its form
    (mirrors ``django.contrib.admin.InlineModelAdmin``). Subclass, set ``model``,
    and list it in a ModelAdmin's ``inlines``::

        class ItemInline(theia_ng.Inline):
            model = OrderItem
            fields = ["product", "qty"]
            extra = 1

        @theia_ng.register(Order)
        class OrderAdmin(theia_ng.ModelAdmin):
            inlines = [ItemInline]

    The child's foreign key back to the parent is set automatically and kept out
    of the inline form (``fk_name`` is auto-detected when there is exactly one
    candidate FK; set it explicitly otherwise).
    """

    model: type[Model]
    fk_name: str | None = None
    # None -> all editable child fields (minus the parent FK).
    fields: list[str] | None = None
    readonly_fields: list[str] = []
    exclude: list[str] = []
    raw_id_fields: list[str] = []
    extra: int = 1
    can_delete: bool = True
    style: str = "tabular"  # "tabular" (grid) | "stacked" (stacked field blocks)
    verbose_name_plural: str | None = None
    display_field: str | None = None

    # Duck-compatibility with the field-descriptor builder / serializer (which
    # read these off a ModelAdmin). Inlines don't use registry/model-field
    # widgets or dependent options.
    registry_choice_fields: list[str] = []
    model_field_select: dict[str, str] = {}
    relation_filters: dict[str, dict[str, str]] = {}

    def display(self, obj: Model) -> str:
        if self.display_field:
            return str(getattr(obj, self.display_field, "") or "")
        return str(obj)


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


def compact_tree(*, description: str = "") -> Callable:
    """Mark a ModelAdmin method as a **compact hierarchy field** — a placeable
    form element that renders the eager subtree (descendants) of the object the
    method returns. Drop its name into ``fields``/``fieldsets`` like any field;
    it is independent of the page's full-hierarchy section and read-only::

        @theia_ng.compact_tree(description="Structure")
        def structure(self, obj):
            return obj            # root the tree at this record (default)
            # return obj.house    # ...or at a related record

    Returning ``None`` hides the element for that record.
    """

    def decorator(func: Callable) -> Callable:
        func._theia_compact_tree = {"description": description}  # type: ignore[attr-defined]
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
    # Extra relations to prefetch for the list query, to avoid N+1 when a
    # relation's label (``__str__`` / ``display()``) or a computed column reaches
    # *across* relations (direct FK fields and ``a__b`` columns are already
    # optimized). Mirrors django admin's ``list_select_related``.
    list_select_related: list[str] = []
    list_prefetch_related: list[str] = []

    # --- list view (inline editing) ---------------------------------------
    # Columns editable directly in the list (must also be in list_display).
    # Non-relation field types are supported; relation columns stay read-only.
    list_editable: list[str] = []

    # --- form view ---------------------------------------------------------
    fields: list[str] | None = None       # None -> all editable fields
    # Group form fields into sections (mirrors django admin's ``fieldsets``)::
    #     fieldsets = [
    #         (None, {"fields": ["name", "category"]}),
    #         ("Advanced", {"fields": ["notes"], "classes": ["collapse"],
    #                       "description": "Rarely changed."}),
    #     ]
    # ``classes`` containing "collapse" makes the section collapsible (collapsed
    # by default). None -> a single, flat, untitled form (current behaviour).
    fieldsets: list | None = None
    # Edit related child rows on this model's form. List of ``Inline`` subclasses.
    inlines: list = []
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
    # Row checkboxes + bulk actions in the list (a built-in "Delete selected" plus
    # any `actions` usable with a selection). Set False to hide them for a model.
    list_selectable: bool = True

    # --- hierarchy tree ----------------------------------------------------
    # Render this model inside a parent→children tree (e.g. Registration →
    # Company → House → Space). The tree always renders from the topmost
    # ancestor, regardless of which level you opened it from.
    #
    # ``tree_parent`` — the forward FK field name leading up to the parent in
    # the hierarchy (``None`` on the root model).
    # ``tree_children`` — reverse-relation accessor names leading down to the
    # children (Django's ``related_name``, or the default ``<model>_set``).
    #
    # e.g. on a House:  tree_parent = "company";  tree_children = ["spaces"]
    # A model with either set advertises a "Hierarchy" view in the SPA.
    tree_parent: str | None = None
    tree_children: list[str] = []

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

    def compact_tree_fields(self) -> list[tuple[str, dict]]:
        """``(name, opts)`` for each ``@compact_tree``-decorated method, in
        declaration order (subclass first). Used to surface them as synthetic
        read-only form fields and to resolve each one's root object per record."""
        seen: set[str] = set()
        out: list[tuple[str, dict]] = []
        for klass in type(self).__mro__:
            for name, attr in vars(klass).items():
                if name in seen:
                    continue
                opts = getattr(attr, "_theia_compact_tree", None)
                if opts is not None:
                    seen.add(name)
                    out.append((name, opts))
        return out

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
