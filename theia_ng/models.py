"""Theia NG models.

``TheiaNgAccess`` is a tableless permission anchor (Django permissions must hang
off a model/content type) — it exists only so ``migrate`` creates the
``theia_ng.access`` entry-gate permission.

``MenuView`` is a real, admin-managed model: named subsets of the sidebar.
"""

from __future__ import annotations

from django.db import models


class TheiaNgAccess(models.Model):
    class Meta:
        managed = False
        default_permissions = ()
        permissions = [("access", "Can access the Theia NG admin")]
        verbose_name = "Theia NG access"


class MenuView(models.Model):
    """A named, admin-defined subset of models for the left sidebar.

    A view only *narrows* the menu within what the user may already see — it
    never grants access (permissions are checked first, then intersected with
    the view). The implicit "Full" view (everything permitted) is not stored.
    """

    name = models.CharField(max_length=100, unique=True)
    position = models.PositiveIntegerField(default=0, help_text="Order in the view selector.")
    # List of "app_label.model_name" keys included in this view.
    model_keys = models.JSONField("Models", default=list, blank=True)
    # Per-model visible fields: {"app.model": ["field", ...]}. Empty list / missing
    # key = all fields. Narrows list columns and form fields (required fields are
    # always shown on create).
    model_fields = models.JSONField("Fields per model", default=dict, blank=True)

    class Meta:
        ordering = ["position", "name"]
        verbose_name = "Menu view"
        verbose_name_plural = "Menu views"

    def __str__(self) -> str:
        return self.name
