"""Optional discovery of ``django.contrib.admin`` registrations.

When ``THEIA_NG['DISCOVER_ADMIN_FILES']`` (or a bare ``DISCOVER_ADMIN_FILES``)
is true, Theia NG imports every app/package ``admin.py`` (via the admin
autodiscover) and, for each model **not already registered with Theia**, builds
a Theia ``ModelAdmin`` from the *compatible* subset of the Django admin's
options. Explicit ``theia.py`` registrations always win.

Only options that translate cleanly are copied — field-based config that means
the same thing in both worlds. Django-specific pieces (callable/method
``list_display`` columns, ``SimpleListFilter`` classes, ``actions``, inlines,
fieldsets, widgets, ``date_hierarchy``, …) are intentionally dropped, so a
discovered model renders with safe defaults rather than broken columns.
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

    # list_select_related only when an explicit relation list (not the bool form).
    lsr = getattr(dj_admin, "list_select_related", False)
    if isinstance(lsr, (list, tuple)) and lsr:
        attrs["list_select_related"] = list(lsr)

    return attrs


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
