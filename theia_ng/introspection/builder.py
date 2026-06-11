"""Build the intermediate representation (IR) from registered models.

Two levels, matching the IR schema (decision #3):

* ``build_registry`` — the lightweight nav/registry payload.
* ``build_model_detail`` — the full per-model descriptor (lazy).

Per-user ``perms`` are baked into the IR (not a separate capabilities call).
The IR should be cached per-deploy with a version key; this module only builds
it — caching lives in the api layer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from theia_ng.introspection.types import FieldType, resolve_field_type

if TYPE_CHECKING:
    from django.db.models import Field, Model
    from django.http import HttpRequest

    from theia_ng.options import ModelAdmin
    from theia_ng.registry import TheiaSite

SCHEMA_VERSION = "1.0"


def _model_key(model: type[Model]) -> str:
    return f"{model._meta.app_label}.{model._meta.model_name}"


def _perms(admin: ModelAdmin, request: HttpRequest) -> dict[str, bool]:
    return {
        "view": admin.has_view_permission(request),
        "add": admin.has_add_permission(request),
        "change": admin.has_change_permission(request),
        "delete": admin.has_delete_permission(request),
    }


def _registry_structure(site: TheiaSite) -> list[dict[str, Any]]:
    """User-independent registry entries (cacheable)."""
    return [
        {
            "key": _model_key(model),
            "verbose_name": str(model._meta.verbose_name),
            "verbose_name_plural": str(model._meta.verbose_name_plural),
            "app_label": model._meta.app_label,
            "app_verbose_name": str(model._meta.app_config.verbose_name),
        }
        for model in site.registry
    ]


def build_registry(site: TheiaSite, request: HttpRequest) -> dict[str, Any]:
    """Lightweight payload for the left nav. Only models the user may view."""
    from theia_ng.cache import cached_structure

    structure = cached_structure("registry", lambda: _registry_structure(site))
    models_out = []
    for entry in structure:
        resolved = site.get_model(entry["key"])
        if resolved is None:
            continue  # model unregistered since the structure was cached
        _, admin = resolved
        perms = _perms(admin, request)
        if not perms["view"]:
            continue
        models_out.append({**entry, "perms": perms})
    return {
        "schema_version": SCHEMA_VERSION,
        "site": {"title": site.site_title},
        "models": models_out,
    }


def _relation_display_field(target: type[Model]) -> str:
    """Pick the field carrying a relation target's option label.

    Defaults to ``"__str__"`` (the target's ``__str__`` / ModelAdmin ``display()``)
    so labels read like the object, not a single column. A target ModelAdmin can
    set ``display_field`` to render one concrete field instead.
    """
    from theia_ng.registry import site

    resolved = site.get_model(_model_key(target))
    if resolved is not None:
        _, target_admin = resolved
        if target_admin.display_field:
            return target_admin.display_field
    return "__str__"


def _relation_descriptor(
    field: Field, ftype: FieldType, source: type[Model], admin: ModelAdmin
) -> dict[str, Any]:
    from theia_ng.registry import site

    target = field.related_model
    target_key = _model_key(target)
    desc: dict[str, Any] = {
        "kind": "m2m" if ftype is FieldType.M2M else "fk",
        "target": target_key,
        "display_field": _relation_display_field(target),
        "options_endpoint": f"data/{target_key}/",
        "searchable": True,
        # Whether the target model is registered with Theia. Unregistered targets
        # have no options/CRUD endpoint, so the SPA renders a raw FK input (or a
        # locked M2M) rather than a picker.
        "registered": site.get_model(target_key) is not None,
        # raw_id_fields: render as a plain id input instead of a picker.
        "raw": field.name in (admin.raw_id_fields or []),
    }
    # Dependent options: route to the context-aware endpoint + declare which
    # sibling fields the options depend on (so the SPA re-fetches on change).
    spec = (admin.relation_filters or {}).get(field.name)
    if spec:
        desc["options_endpoint"] = f"relation-options/{_model_key(source)}/{field.name}/"
        desc["depends_on"] = list(spec.values())
    return desc


def _serialize_default(field: Field) -> Any:
    """JSON-safe static default, or None.

    Callable defaults (e.g. ``timezone.now``, ``uuid4``) are intentionally NOT
    invoked at schema-build time — they resolve at insert time on the server.
    """
    if not field.has_default():
        return None
    default = field.default
    if callable(default):
        return None
    if isinstance(default, (str, int, float, bool)):
        return default
    return None  # non-scalar default (e.g. list/dict) — let the form start empty


def _titleize(name: str) -> str:
    """`full_name` -> `Full Name` (label for a computed list_display column)."""
    return name.replace("_", " ").title()


def _column_label(model: type[Model], admin: ModelAdmin, name: str) -> str:
    """Header label for a list_display column (field, property, or admin method).
    Honours a ``short_description`` (set by ``@theia_ng.display`` or directly)."""
    from django.core.exceptions import FieldDoesNotExist

    method = getattr(admin, name, None)
    if callable(method):
        return str(getattr(method, "short_description", None) or _titleize(name))
    try:
        return _humanize_label(model._meta.get_field(name))
    except FieldDoesNotExist:
        pass
    attr = getattr(model, name, None)
    if attr is not None:
        return str(getattr(attr, "short_description", None) or _titleize(name))
    return _titleize(name)


def _humanize_label(field: Field) -> str:
    """Human field label. Django auto-derives ``verbose_name`` from the field
    name (``is_active`` -> ``is active``); title-case those so multi-word labels
    read as ``Is Active``. An explicitly-set ``verbose_name`` is left untouched."""
    verbose = str(getattr(field, "verbose_name", "") or field.name)
    if verbose == field.name.replace("_", " "):
        return verbose.title()
    return verbose


def _field_descriptor(field: Field, source: type[Model], admin: ModelAdmin) -> dict[str, Any]:
    ftype = resolve_field_type(field)
    out: dict[str, Any] = {
        "name": field.name,
        "label": _humanize_label(field),
        "type": ftype.value,
        "required": not field.blank,
        "editable": field.editable,
        # read_only = "show in the form but disabled" (set for readonly_fields).
        # Plain non-editable fields (auto pk/timestamps) just stay out of the form
        # via editable=False; only readonly_fields opt them back in, read-only.
        "read_only": False,
        "help_text": str(getattr(field, "help_text", "")),
        "default": _serialize_default(field),
        "widget": None,
    }
    if ftype is FieldType.CHOICE:
        out["choices"] = [
            {"value": value, "label": str(label)} for value, label in field.choices
        ]
    if ftype in (FieldType.FK, FieldType.M2M):
        out["relation"] = _relation_descriptor(field, ftype, source, admin)
    if max_length := getattr(field, "max_length", None):
        out["constraints"] = {"max_length": max_length}
    return out


def _model_structure(model: type[Model], admin: ModelAdmin) -> dict[str, Any]:
    """User-independent model descriptor (cacheable; excludes ``perms``)."""
    key = _model_key(model)
    # Forward fields only: concrete_fields (scalars + FK) + the declared M2M
    # fields. Using get_fields() here would also yield reverse relations
    # (ManyToManyRel/ManyToOneRel), which have no .blank/.editable.
    field_objs = [*model._meta.concrete_fields, *model._meta.many_to_many]
    fields = [_field_descriptor(f, model, admin) for f in field_objs]

    # ModelAdmin.readonly_fields are non-editable in the IR (and thus the form).
    readonly = set(admin.readonly_fields)
    for field in fields:
        if field["name"] in readonly:
            field["read_only"] = True
            field["editable"] = False

    # ModelAdmin.exclude drops fields from the form (kept in the IR so they can
    # still appear in list_display). exclude wins over readonly.
    excluded = set(admin.exclude)
    for field in fields:
        if field["name"] in excluded:
            field["editable"] = False
            field["read_only"] = False

    # Optional, layered enrichment (model-derived specs stay the base).
    if admin.serializer_class is not None:
        from theia_ng.adapters.drf import enrich_fields_from_serializer

        enrich_fields_from_serializer(fields, admin.serializer_class)
    if admin.openapi_schema is not None:
        from theia_ng.adapters.openapi import enrich_fields_from_openapi

        enrich_fields_from_openapi(fields, admin.openapi_schema, admin.openapi_component)

    return {
        "schema_version": SCHEMA_VERSION,
        "key": key,
        "verbose_name": str(model._meta.verbose_name),
        "endpoints": {
            "list": f"data/{key}/",
            "detail": f"data/{key}/{{pk}}/",
        },
        "list": {
            "display": list(admin.list_display),
            "labels": {name: _column_label(model, admin, name) for name in admin.list_display},
            "filters": list(admin.list_filter),
            "search_fields": list(admin.search_fields),
            "ordering": list(admin.ordering),
            "per_page": admin.list_per_page,
        },
        "fields": fields,
        "actions": [{"key": a, "label": a, "endpoint": f"action/{key}/{a}/"} for a in admin.actions],
    }


def build_model_detail(
    model: type[Model], admin: ModelAdmin, request: HttpRequest
) -> dict[str, Any]:
    from theia_ng.cache import cached_structure

    structure = cached_structure(
        f"model:{_model_key(model)}", lambda: _model_structure(model, admin)
    )
    # Merge per-user perms fresh (never cached).
    return {**structure, "perms": _perms(admin, request)}
