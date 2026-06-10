"""Access gate for Theia NG.

Deliberately does NOT reuse ``User.is_staff`` (that flag means "can access the
*django* admin site"). Instead Theia NG defines its own access permission so it
never collides with a project that also runs django.contrib.admin.

The permission is created on ``migrate`` via the unmanaged ``TheiaNgAccess``
anchor model (see ``theia_ng.models`` + migration ``0001``). ``has_access`` is
the single seam host projects override (e.g. to map iBar's Registration roles).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django.http import HttpRequest

# The codename a user needs to open the admin at all.
ACCESS_PERM = "theia_ng.access"


def has_access(request: HttpRequest) -> bool:
    user = getattr(request, "user", None)
    if not (user and user.is_authenticated and user.is_active):
        return False
    if user.is_superuser:
        return True
    return user.has_perm(ACCESS_PERM)
