"""Session login/logout for the SPA.

Theia NG uses Django session auth (same origin). The SPA calls ``me`` on boot:
it reports the current user and seeds the CSRF cookie (``@ensure_csrf_cookie``),
so the subsequent ``login`` POST carries a valid ``X-CSRFToken``.

Uses Django's standard ``authenticate``/``login``, so the host project's
configured AUTHENTICATION_BACKENDS (and custom user model) are respected.
"""

from __future__ import annotations

import json

from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie

from theia_ng.permissions import has_access


def _first_name(user) -> str | None:
    """First name for the greeting, if the user model carries one (non-fatal:
    custom user models may not have ``first_name``)."""
    name = (getattr(user, "first_name", "") or "").strip()
    return name or None


def _payload(request: HttpRequest) -> dict:
    user = request.user
    authenticated = bool(user.is_authenticated)
    return {
        "authenticated": authenticated,
        "username": user.get_username() if authenticated else None,
        "first_name": _first_name(user) if authenticated else None,
        "is_superuser": bool(getattr(user, "is_superuser", False)) if authenticated else False,
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


def change_password(request: HttpRequest) -> JsonResponse:
    """Self-service: the signed-in user changes their own password, verifying the
    current one first. Keeps the session valid (``update_session_auth_hash``) and
    runs the project's configured password validators on the new value."""
    if request.method != "POST":
        return JsonResponse({"detail": "Method not allowed"}, status=405)
    if not request.user.is_authenticated or not has_access(request):
        return JsonResponse({"detail": "Forbidden"}, status=403)
    try:
        data = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"detail": "Invalid JSON body"}, status=400)

    user = request.user
    current = data.get("current_password") or ""
    new = data.get("new_password") or ""
    if not user.check_password(current):
        return JsonResponse({"detail": "Current password is incorrect."}, status=400)
    try:
        validate_password(new, user=user)
    except DjangoValidationError as exc:
        return JsonResponse({"detail": " ".join(exc.messages)}, status=400)
    user.set_password(new)
    user.save()
    update_session_auth_hash(request, user)  # keep the user signed in
    return JsonResponse({"ok": True})
