"""Permission anchor.

Theia NG has no real data models — it operates on the host project's models. But
Django permissions must hang off a model/content type. This unmanaged model has
NO database table (``managed = False``); it exists only so ``migrate`` creates
the ``theia_ng.access`` permission (the admin's entry gate — see
``theia_ng.permissions``). We strip the default add/change/delete/view perms.
"""

from __future__ import annotations

from django.db import models


class TheiaNgAccess(models.Model):
    class Meta:
        managed = False
        default_permissions = ()
        permissions = [("access", "Can access the Theia NG admin")]
        verbose_name = "Theia NG access"
