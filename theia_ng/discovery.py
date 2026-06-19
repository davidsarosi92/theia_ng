"""Optional discovery of ``django.contrib.admin`` registrations.

When ``THEIA_NG['DISCOVER_ADMIN_FILES']`` (or a bare ``DISCOVER_ADMIN_FILES``)
is true, Theia NG imports every app/package ``admin.py`` (via the admin
autodiscover) and, for each model **not already registered with Theia**, builds
a Theia ``ModelAdmin`` from the *compatible* subset of the Django admin's
options. Explicit ``theia.py`` registrations always win.

Only options that translate cleanly are copied — field-based config that means
the same thing in both worlds. ``fieldsets``, ``list_editable`` and ``inlines``
(``TabularInline``/``StackedInline``) are translated to their Theia equivalents.
Django-specific pieces (callable/method ``list_display`` columns,
``SimpleListFilter`` classes, ``actions``, custom widgets, ``date_hierarchy``, …)
are still dropped, so a discovered model renders with safe defaults rather than
broken columns.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from django.db.models import Model

    from theia_ng.registry import TheiaSite


def _enabled() -> bool:
    from django.conf import settings

    conf = getattr(settings, "THEIA_NG", {}) or {}
    if "DISCOVER_ADMIN_FILES" in conf:
        return bool(conf["DISCOVER_ADMIN_FILES"])
    return bool(getattr(settings, "DISCOVER_ADMIN_FILES", False))


def _is_real_field(model: type[Model], name: Any) -> bool:
    from django.core.exceptions import FieldDoesNotExist

    if not isinstance(name, str):
        return False
    try:
        model._meta.get_field(name)
        return True
    except (FieldDoesNotExist, Exception):
        return False


def _is_field_or_lookup(model: type[Model], name: Any) -> bool:
    if not isinstance(name, str):
        return False  # callable / admin-method column — not portable
    if "__" in name:
        from theia_ng.introspection.builder import _resolve_lookup_field

        return _resolve_lookup_field(model, name) is not None
    return _is_real_field(model, name)


def _str_list(value: Any) -> list[str]:
    if not value:
        return []
    return [v for v in value if isinstance(v, str)]


def translate_admin(model: type[Model], dj_admin: Any) -> dict[str, Any]:
    """The compatible Theia ``ModelAdmin`` attributes for a Django ModelAdmin."""
    attrs: dict[str, Any] = {}

    # list_display: real fields + a__b lookups only (drop callables/methods/__str__).
    display = [n for n in (getattr(dj_admin, "list_display", ()) or ()) if _is_field_or_lookup(model, n)]
    if display:
        attrs["list_display"] = display

    # list_filter: only plain field-name strings (SimpleListFilter classes use a
    # different API and are skipped).
    filters = [n for n in (getattr(dj_admin, "list_filter", ()) or ()) if _is_field_or_lookup(model, n)]
    if filters:
        attrs["list_filter"] = filters

    # search_fields / ordering: ORM lookups — identical meaning, copy as-is.
    for opt in ("search_fields", "ordering"):
        vals = _str_list(getattr(dj_admin, opt, ()))
        if vals:
            attrs[opt] = vals

    per_page = getattr(dj_admin, "list_per_page", None)
    if isinstance(per_page, int):
        attrs["list_per_page"] = per_page

    # field name lists — keep only entries that are real fields. (Django defaults
    # exclude/fields to None, so coerce before iterating.)
    for opt in ("readonly_fields", "exclude", "raw_id_fields"):
        vals = [n for n in (getattr(dj_admin, opt, ()) or ()) if _is_real_field(model, n)]
        if vals:
            attrs[opt] = vals

    # `fields` only if it's a flat list of real field names (skip fieldset rows).
    fields = getattr(dj_admin, "fields", None)
    if fields and all(_is_real_field(model, f) for f in fields):
        attrs["fields"] = list(fields)

    # list_editable: real fields that are also shown as columns.
    shown = set(attrs.get("list_display", []))
    editable = [
        n
        for n in (getattr(dj_admin, "list_editable", ()) or ())
        if _is_real_field(model, n) and n in shown
    ]
    if editable:
        attrs["list_editable"] = editable

    # fieldsets: same shape in both worlds; keep sections whose fields are real
    # (entries may be tuples grouping several fields on a row — validate each).
    fieldsets = _translate_fieldsets(model, getattr(dj_admin, "fieldsets", None))
    if fieldsets:
        attrs["fieldsets"] = fieldsets

    # inlines: map each django InlineModelAdmin to a Theia Inline subclass.
    inlines = _translate_inlines(getattr(dj_admin, "inlines", ()) or ())
    if inlines:
        attrs["inlines"] = inlines

    # list_select_related only when an explicit relation list (not the bool form).
    lsr = getattr(dj_admin, "list_select_related", False)
    if isinstance(lsr, (list, tuple)) and lsr:
        attrs["list_select_related"] = list(lsr)

    return attrs


def _flatten(fields: Any) -> list[str]:
    out: list[str] = []
    for f in fields or ():
        if isinstance(f, (list, tuple)):
            out.extend(x for x in f if isinstance(x, str))
        elif isinstance(f, str):
            out.append(f)
    return out


def _translate_fieldsets(model: type[Model], fieldsets: Any) -> list | None:
    if not fieldsets:
        return None
    out: list = []
    for entry in fieldsets:
        try:
            name, opts = entry
        except (TypeError, ValueError):
            continue
        opts = opts or {}
        if not all(_is_real_field(model, f) for f in _flatten(opts.get("fields"))):
            continue  # references a non-field (callable/computed) — skip the section
        out.append((name, dict(opts)))
    return out or None


def _translate_inlines(dj_inlines: Any) -> list:
    from theia_ng.options import Inline

    out: list = []
    for dj_inline in dj_inlines:
        child = getattr(dj_inline, "model", None)
        if child is None:
            continue
        iattrs: dict[str, Any] = {"model": child}
        if fk := getattr(dj_inline, "fk_name", None):
            iattrs["fk_name"] = fk
        for opt in ("readonly_fields", "exclude", "raw_id_fields"):
            vals = [n for n in (getattr(dj_inline, opt, ()) or ()) if _is_real_field(child, n)]
            if vals:
                iattrs[opt] = vals
        f = getattr(dj_inline, "fields", None)
        if f and all(_is_real_field(child, x) for x in _flatten(f)):
            iattrs["fields"] = _flatten(f)
        extra = getattr(dj_inline, "extra", None)
        if isinstance(extra, int):
            iattrs["extra"] = extra
        can_delete = getattr(dj_inline, "can_delete", None)
        if isinstance(can_delete, bool):
            iattrs["can_delete"] = can_delete
        template = str(getattr(dj_inline, "template", "") or "").lower()
        iattrs["style"] = "stacked" if "stacked" in template else "tabular"
        out.append(type(f"{child.__name__}DiscoveredInline", (Inline,), iattrs))
    return out


def discover_django_admins(site: TheiaSite) -> int:
    """Register every Django-admin model that Theia doesn't already cover, using
    its compatible options. Returns the number of models discovered. No-op (and
    never raises) unless explicitly enabled."""
    if not _enabled():
        return 0
    try:
        from django.contrib import admin

        admin.autodiscover()  # import all app/package admin.py (idempotent)
    except Exception:
        return 0

    from theia_ng.options import ModelAdmin

    discovered = 0
    for model, dj_admin in list(getattr(admin.site, "_registry", {}).items()):
        if site.is_registered(model):
            continue  # explicit theia.py registration wins
        try:
            attrs = translate_admin(model, dj_admin)
            admin_cls = type(f"{model.__name__}DiscoveredAdmin", (ModelAdmin,), attrs)
            site.register(model, admin_cls)
            discovered += 1
        except Exception:
            continue  # one bad admin must not break the rest
    return discovered
