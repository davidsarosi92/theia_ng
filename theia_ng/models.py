"""Theia NG models.

``TheiaNgAccess`` is a tableless permission anchor (Django permissions must hang
off a model/content type) — it exists only so ``migrate`` creates the
``theia_ng.access`` entry-gate permission.

``MenuView`` is a real, admin-managed model: named subsets of the sidebar.
"""

from __future__ import annotations

from django.conf import settings
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


class LogEntry(models.Model):
    """An audit record of a single write through Theia NG.

    One row per create / update / delete / custom action. ``changes`` holds the
    field-level diff (``{field: [old, new]}``) for create/update. ``username`` is
    snapshotted so the trail survives the user being deleted.
    """

    CREATE, UPDATE, DELETE, ACTION = "create", "update", "delete", "action"
    ACTIONS = [
        (CREATE, "Create"),
        (UPDATE, "Update"),
        (DELETE, "Delete"),
        (ACTION, "Action"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="theia_ng_logs",
    )
    username = models.CharField(max_length=255, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    action = models.CharField(max_length=16, choices=ACTIONS)
    model_key = models.CharField(max_length=120, db_index=True)
    object_pk = models.CharField(max_length=64, blank=True)
    object_repr = models.CharField(max_length=255, blank=True)
    # Field-level diff {field: [old, new]}, or action metadata.
    changes = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-timestamp"]
        verbose_name = "Log entry"
        verbose_name_plural = "Log entries"
        indexes = [models.Index(fields=["user", "-timestamp"])]

    def __str__(self) -> str:
        return f"{self.action} {self.model_key} #{self.object_pk} by {self.username}"


class Favorite(models.Model):
    """A user's favorite models for the home page, stored as an ordered list of
    ``app_label.model_name`` keys. One row per user (a personal shortcut list;
    the home page intersects it with what the user may actually see)."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="theia_ng_favorites",
    )
    model_keys = models.JSONField(default=list, blank=True)

    class Meta:
        verbose_name = "Favorite"
        verbose_name_plural = "Favorites"

    def __str__(self) -> str:
        return f"Favorites for {self.user}"
