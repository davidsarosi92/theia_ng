"""Per-user home-page favorites.

A personal, ordered list of ``app_label.model_name`` keys, stored server-side so
it follows the user across devices. The home page intersects it with what the
user may actually see, so stale keys (revoked models) simply drop out.

* ``GET  favorites/`` → ``{"favorites": [key, ...]}``
* ``PUT  favorites/`` body ``{"favorites": [key, ...]}`` → replaces the list

Session auth (same origin), so the PUT carries the CSRF token like the other
write endpoints. Gated by ``has_access``.
"""

from __future__ import annotations

import json

from django.http import HttpRequest, JsonResponse

from theia_ng.permissions import has_access


def _keys_for(user) -> list[str]:
    from theia_ng.models import Favorite

    row = Favorite.objects.filter(user=user).first()
    return list(row.model_keys) if row else []


def favorites(request: HttpRequest) -> JsonResponse:
    if not has_access(request):
        return JsonResponse({"detail": "Forbidden"}, status=403)
    user = request.user

    if request.method == "GET":
        return JsonResponse({"favorites": _keys_for(user)})

    if request.method == "PUT":
        from theia_ng.models import Favorite

        try:
            data = json.loads(request.body or b"{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({"detail": "Invalid JSON body"}, status=400)
        raw = data.get("favorites")
        if not isinstance(raw, list) or not all(isinstance(k, str) for k in raw):
            return JsonResponse({"detail": "`favorites` must be a list of strings"}, status=400)
        # De-dupe while preserving order.
        seen: set[str] = set()
        keys = [k for k in raw if not (k in seen or seen.add(k))]
        Favorite.objects.update_or_create(user=user, defaults={"model_keys": keys})
        return JsonResponse({"favorites": keys})

    return JsonResponse({"detail": "Method not allowed"}, status=405)
