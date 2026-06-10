"""The closed IR type system.

The Angular bundle maps each of these 16 types to a default widget. Anything
that does not fit falls back to ``json`` (+ an optional ``widget`` hint a plugin
can override) — the UI never breaks on an unknown field.
"""

from __future__ import annotations

import enum

from django.db import models


class FieldType(str, enum.Enum):
    STRING = "string"
    TEXT = "text"
    INTEGER = "integer"
    DECIMAL = "decimal"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"
    TIME = "time"
    EMAIL = "email"
    URL = "url"
    UUID = "uuid"
    JSON = "json"
    CHOICE = "choice"
    FK = "fk"
    M2M = "m2m"
    FILE = "file"
    IMAGE = "image"


# Order matters: more specific subclasses must be checked before their bases.
_FIELD_MAP: list[tuple[type[models.Field], FieldType]] = [
    (models.ImageField, FieldType.IMAGE),
    (models.FileField, FieldType.FILE),
    (models.EmailField, FieldType.EMAIL),
    (models.URLField, FieldType.URL),
    (models.UUIDField, FieldType.UUID),
    (models.JSONField, FieldType.JSON),
    (models.TextField, FieldType.TEXT),
    (models.BooleanField, FieldType.BOOLEAN),
    (models.DateTimeField, FieldType.DATETIME),
    (models.DateField, FieldType.DATE),
    (models.TimeField, FieldType.TIME),
    (models.DecimalField, FieldType.DECIMAL),
    (models.FloatField, FieldType.DECIMAL),
    (models.IntegerField, FieldType.INTEGER),
    (models.CharField, FieldType.STRING),
]


def resolve_field_type(field: models.Field) -> FieldType:
    """Map a Django field to its closed IR type.

    Relations and choices take precedence; everything else falls back through
    ``_FIELD_MAP`` and finally to ``json``.
    """
    if isinstance(field, models.ManyToManyField):
        return FieldType.M2M
    if isinstance(field, (models.ForeignKey, models.OneToOneField)):
        return FieldType.FK
    if getattr(field, "choices", None):
        return FieldType.CHOICE
    for cls, ftype in _FIELD_MAP:
        if isinstance(field, cls):
            return ftype
    return FieldType.JSON
