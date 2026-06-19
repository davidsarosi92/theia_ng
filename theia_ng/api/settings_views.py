"""Per-user UI settings (language, timezone, theme, sidebar order).

A personal preferences blob stored server-side so it follows the user across
devices. Every value has a *default sourced from Django* — an empty stored
``language``/``timezone`` resolves to ``get_language()`` / the active timezone,
so the SPA always receives concrete values to apply.

* ``GET   settings/`` → ``{"language", "timezone", "theme", "nav_order",
  "available_languages"}`` (defaults filled in)
* ``PATCH settings/`` body with any subset of ``language``/``timezone``/
  ``theme``/``nav_order`` → persists and returns the merged settings

Session auth (same origin), so the PATCH carries the CSRF token like the other
write endpoints. Gated by ``has_access``.
"""

from __future__ import annotations

import json

from django.http import HttpRequest, JsonResponse
from django.utils import timezone as django_tz
from django.utils import translation

from theia_ng.permissions import has_access

# UI languages theia ships translations for. Keep in sync with the SPA's
# runtime translation dictionary (``frontend/src/app/i18n/``).
SUPPORTED_LANGUAGES: list[dict[str, str]] = [
    {"code": "en", "label": "English"},
    {"code": "hu", "label": "Magyar"},
    {"code": "de", "label": "Deutsch"},
    {"code": "fr", "label": "Français"},
    {"code": "zh", "label": "中文"},
    {"code": "ko", "label": "한국어"},
    {"code": "ru", "label": "Русский"},
    {"code": "es", "label": "Español"},
    {"code": "tr", "label": "Türkçe"},
]
_LANG_CODES = {entry["code"] for entry in SUPPORTED_LANGUAGES}
_THEMES = {"auto", "light", "dark"}


def _default_language() -> str:
    """Django's active UI language, narrowed to a supported base code."""
    active = (translation.get_language() or "en").lower()
    if active in _LANG_CODES:
        return active
    base = active.split("-")[0]  # e.g. "en-us" -> "en"
    return base if base in _LANG_CODES else "en"


def _default_timezone() -> str:
    return str(django_tz.get_current_timezone_name())


def _effective(user) -> dict:
    """The user's stored settings, with Django defaults filled in for blanks."""
    from theia_ng.models import UserSettings

    row = UserSettings.objects.filter(user=user).first()
    return {
        "language": (row.language if row and row.language else _default_language()),
        "timezone": (row.timezone if row and row.timezone else _default_timezone()),
        "theme": (row.theme if row else UserSettings.THEME_AUTO),
        "nav_app_order": (list(row.nav_app_order) if row and row.nav_app_order else []),
        "nav_order": (list(row.nav_order) if row and row.nav_order else []),
    }


def _clean_str_list(value):
    """Validate a list-of-strings and de-dupe preserving order, or None if invalid."""
    if not isinstance(value, list) or not all(isinstance(k, str) for k in value):
        return None
    seen: set[str] = set()
    return [k for k in value if not (k in seen or seen.add(k))]


def settings(request: HttpRequest) -> JsonResponse:
    if not has_access(request):
        return JsonResponse({"detail": "Forbidden"}, status=403)
    user = request.user

    if request.method == "GET":
        return JsonResponse({**_effective(user), "available_languages": SUPPORTED_LANGUAGES})

    if request.method == "PATCH":
        from theia_ng.models import UserSettings

        try:
            data = json.loads(request.body or b"{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({"detail": "Invalid JSON body"}, status=400)
        if not isinstance(data, dict):
            return JsonResponse({"detail": "Body must be a JSON object"}, status=400)

        defaults: dict = {}
        if "language" in data:
            lang = data["language"]
            if lang not in _LANG_CODES:
                return JsonResponse({"detail": f"Unsupported language: {lang!r}"}, status=400)
            defaults["language"] = lang
        if "timezone" in data:
            tz = data["timezone"]
            if not isinstance(tz, str) or not tz:
                return JsonResponse({"detail": "`timezone` must be a non-empty string"}, status=400)
            defaults["timezone"] = tz[:64]
        if "theme" in data:
            theme = data["theme"]
            if theme not in _THEMES:
                return JsonResponse({"detail": f"Unsupported theme: {theme!r}"}, status=400)
            defaults["theme"] = theme
        if "nav_app_order" in data:
            cleaned = _clean_str_list(data["nav_app_order"])
            if cleaned is None:
                return JsonResponse({"detail": "`nav_app_order` must be a list of strings"}, status=400)
            defaults["nav_app_order"] = cleaned
        if "nav_order" in data:
            cleaned = _clean_str_list(data["nav_order"])
            if cleaned is None:
                return JsonResponse({"detail": "`nav_order` must be a list of strings"}, status=400)
            defaults["nav_order"] = cleaned

        if defaults:
            UserSettings.objects.update_or_create(user=user, defaults=defaults)
        return JsonResponse(_effective(user))

    return JsonResponse({"detail": "Method not allowed"}, status=405)
