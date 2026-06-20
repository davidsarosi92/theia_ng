"""Admin-editable site config: override settings.py THEIA_NG from the UI.

Superuser-only. Lets an admin override the runtime-safe deploy settings
(SITE_TITLE, LOGO_URL, SCHEMA_TTL, CACHE_VERSION), reset them back to settings.py,
and flush the cached IR.

* ``GET    site-config/``             → {defaults, overrides, effective, cache_buster}
* ``PATCH  site-config/`` body subset → save overrides (empty/null clears a field)
* ``DELETE site-config/``             → reset all overrides to settings.py
* ``POST   site-config/clear-cache/`` → bump cache_buster (flush the IR cache)

The defaults block lets the form show each setting's settings.py value as a hint.
"""

from __future__ import annotations

import json

from django.http import HttpRequest, JsonResponse


def _is_admin(request: HttpRequest) -> bool:
    user = getattr(request, "user", None)
    return bool(user and user.is_authenticated and user.is_active and user.is_superuser)


def _payload() -> dict:
    from theia_ng.models import SiteConfig
    from theia_ng.siteconfig import logo_url as resolve_logo
    from theia_ng.siteconfig import settings_conf

    row = SiteConfig.objects.filter(pk=SiteConfig.SINGLETON_PK).first()
    defaults = settings_conf()
    overrides = {
        "site_title": (row.site_title if row else "") or "",
        "logo_url": (row.logo_url if row else "") or "",
        "schema_ttl": (row.schema_ttl if row else None),
        "cache_version": (row.cache_version if row else "") or "",
    }
    effective = {
        "site_title": overrides["site_title"] or defaults.get("SITE_TITLE", "Theia NG Admin"),
        # Resolved for an <img src> (static paths expanded), matching the topbar.
        "logo_url": resolve_logo(),
        "schema_ttl": overrides["schema_ttl"] if overrides["schema_ttl"] is not None
        else int(defaults.get("SCHEMA_TTL", 300)),
        "cache_version": overrides["cache_version"] or str(defaults.get("CACHE_VERSION", "")),
    }
    return {
        "defaults": {
            "site_title": defaults.get("SITE_TITLE", "Theia NG Admin"),
            "logo_url": defaults.get("LOGO_URL", "") or "",
            "schema_ttl": int(defaults.get("SCHEMA_TTL", 300)),
            "cache_version": str(defaults.get("CACHE_VERSION", "")),
        },
        "overrides": overrides,
        "effective": effective,
        "cache_buster": (row.cache_buster if row else 0),
    }


def site_config(request: HttpRequest) -> JsonResponse:
    if not _is_admin(request):
        return JsonResponse({"detail": "Forbidden"}, status=403)

    from theia_ng.models import SiteConfig

    if request.method == "GET":
        return JsonResponse(_payload())

    if request.method == "PATCH":
        try:
            data = json.loads(request.body or b"{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({"detail": "Invalid JSON body"}, status=400)
        if not isinstance(data, dict):
            return JsonResponse({"detail": "Body must be a JSON object"}, status=400)

        row, _ = SiteConfig.objects.get_or_create(pk=SiteConfig.SINGLETON_PK)
        if "site_title" in data:
            row.site_title = (data["site_title"] or "")[:200]
        if "logo_url" in data:
            row.logo_url = (data["logo_url"] or "")[:500]
        if "cache_version" in data:
            row.cache_version = (data["cache_version"] or "")[:50]
        if "schema_ttl" in data:
            ttl = data["schema_ttl"]
            if ttl in (None, ""):
                row.schema_ttl = None
            else:
                try:
                    ttl = int(ttl)
                except (TypeError, ValueError):
                    return JsonResponse({"detail": "`schema_ttl` must be an integer"}, status=400)
                if ttl < 0:
                    return JsonResponse({"detail": "`schema_ttl` must be >= 0"}, status=400)
                row.schema_ttl = ttl
        row.save()
        return JsonResponse(_payload())

    if request.method == "DELETE":
        # Reset: drop every override, falling back to settings.py.
        SiteConfig.objects.filter(pk=SiteConfig.SINGLETON_PK).delete()
        return JsonResponse(_payload())

    return JsonResponse({"detail": "Method not allowed"}, status=405)


def clear_cache(request: HttpRequest) -> JsonResponse:
    """Flush the cached IR by bumping the cache-buster generation."""
    if not _is_admin(request):
        return JsonResponse({"detail": "Forbidden"}, status=403)
    if request.method != "POST":
        return JsonResponse({"detail": "Method not allowed"}, status=405)

    from django.db.models import F

    from theia_ng.models import SiteConfig

    row, _ = SiteConfig.objects.get_or_create(pk=SiteConfig.SINGLETON_PK)
    SiteConfig.objects.filter(pk=row.pk).update(cache_buster=F("cache_buster") + 1)
    row.refresh_from_db()
    return JsonResponse({"detail": "ok", "cache_buster": row.cache_buster})
