"""Session login/logout for the SPA.

Theia NG uses Django session auth (same origin). The SPA calls ``me`` on boot:
it reports the current user and seeds the CSRF cookie (``@ensure_csrf_cookie``),
so the subsequent ``login`` POST carries a valid ``X-CSRFToken``.

Uses Django's standard ``authenticate``/``login``, so the host project's
configured AUTHENTICATION_BACKENDS (and custom user model) are respected.
"""

from __future__ import annotations

import json

from django.contrib.auth import authenticate, login, logout
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie

from theia_ng.permissions import has_access


def _payload(request: HttpRequest) -> dict:
    user = request.user
    authenticated = bool(user.is_authenticated)
    return {
        "authenticated": authenticated,
        "username": user.get_username() if authenticated else None,
        "can_access": has_access(request),
    }


@ensure_csrf_cookie
def me(request: HttpRequest) -> JsonResponse:
    """Current auth state. Also seeds the CSRF cookie for the login POST."""
    return JsonResponse(_payload(request))


def login_view(request: HttpRequest) -> JsonResponse:
    if request.method != "POST":
        return JsonResponse({"detail": "Method not allowed"}, status=405)
    try:
        data = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"detail": "Invalid JSON body"}, status=400)

    user = authenticate(request, username=data.get("username"), password=data.get("password"))
    if user is None:
        return JsonResponse({"detail": "Invalid credentials"}, status=400)
    login(request, user)
    return JsonResponse(_payload(request))


def logout_view(request: HttpRequest) -> JsonResponse:
    if request.method != "POST":
        return JsonResponse({"detail": "Method not allowed"}, status=405)
    logout(request)
    return JsonResponse({"authenticated": False, "username": None, "can_access": False})
