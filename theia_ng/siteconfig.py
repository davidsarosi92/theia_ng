"""Effective Theia NG config: ``settings.THEIA_NG`` overlaid with admin overrides.

The ``SiteConfig`` singleton lets an admin override a runtime-safe subset of the
deploy config (SITE_TITLE, LOGO_URL, SCHEMA_TTL, CACHE_VERSION) from the UI, with
a one-click reset back to settings.py. Everything that reads THEIA_NG config goes
through ``conf()`` here so the override is honoured consistently (cache keys, the
topbar title/logo, the injected SPA config).

DB access is lazy and defensive: before the table is migrated (or if the DB is
down) it silently falls back to settings.py, so importing this never breaks boot.
"""

from __future__ import annotations

from typing import Any

from django.conf import settings

# Keys an admin may override from the UI (others are structural / deploy-only).
OVERRIDABLE = ("SITE_TITLE", "LOGO_URL", "SCHEMA_TTL", "CACHE_VERSION")


def _row():
    try:
        from theia_ng.models import SiteConfig

        return SiteConfig.objects.filter(pk=SiteConfig.SINGLETON_PK).first()
    except Exception:
        return None  # table not migrated yet / DB unavailable


def overrides() -> dict[str, Any]:
    """Only the override fields that are actually set (empty/null = no override)."""
    row = _row()
    if row is None:
        return {}
    out: dict[str, Any] = {}
    if row.site_title:
        out["SITE_TITLE"] = row.site_title
    if row.logo_url:
        out["LOGO_URL"] = row.logo_url
    if row.schema_ttl is not None:
        out["SCHEMA_TTL"] = row.schema_ttl
    if row.cache_version:
        out["CACHE_VERSION"] = row.cache_version
    return out


def conf() -> dict[str, Any]:
    """settings.THEIA_NG with the admin overrides applied on top."""
    base = dict(getattr(settings, "THEIA_NG", {}) or {})
    base.update(overrides())
    return base


def settings_conf() -> dict[str, Any]:
    """The raw settings.py THEIA_NG dict (the defaults a reset restores to)."""
    return dict(getattr(settings, "THEIA_NG", {}) or {})


def logo_url() -> str:
    """The effective logo URL, ready for an ``<img src>``.

    An absolute URL (``http(s)://``, ``//``, a root-relative ``/path``, or a
    ``data:`` URI) is used as-is. Anything else is treated as a Django static
    path and resolved through ``static()`` — so an admin can enter
    ``admin/imgs/logo.png`` and get ``{STATIC_URL}admin/imgs/logo.png``."""
    raw = (conf().get("LOGO_URL") or "").strip()
    if not raw or raw.startswith(("http://", "https://", "//", "/", "data:")):
        return raw
    try:
        from django.templatetags.static import static

        return static(raw)
    except Exception:
        return raw


def cache_buster() -> int:
    """Generation counter folded into IR cache keys; bumped to flush the cache."""
    row = _row()
    return int(row.cache_buster) if row else 0
