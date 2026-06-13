"""Instance <-> JSON serialization for the auto-CRUD layer.

Maps Django field values to JSON-safe shapes consistent with the IR type
system. Relations use a uniform ``{"id", "label"}`` shape (list for M2M) so the
frontend renders them the same way in list and detail views.
"""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from django.db import models

if TYPE_CHECKING:
    from theia_ng.options import ModelAdmin

# --- field selection -------------------------------------------------------


def serializable_fields(model: type[models.Model]) -> list[models.Field]:
    """Concrete local fields (incl. pk) + many-to-many."""
    out: list[models.Field] = []
    for field in model._meta.get_fields():
        if isinstance(field, models.ManyToManyField):
            out.append(field)
        elif getattr(field, "concrete", False):
            out.append(field)
    return out


def editable_fields(model: type[models.Model], admin: ModelAdmin) -> list[models.Field]:
    """Fields a client may write: editable, not read-only, not excluded, not auto."""
    skip = set(admin.readonly_fields) | set(admin.exclude)
    out: list[models.Field] = []
    for field in model._meta.get_fields():
        if getattr(field, "auto_created", False) or field.name in skip:
            continue
        if isinstance(field, models.ManyToManyField):
            if field.editable:
                out.append(field)
        elif getattr(field, "concrete", False) and field.editable:
            out.append(field)
    return out


def relation_field_names(fields: list[models.Field]) -> tuple[list[str], list[str]]:
    """Split a field list into (fk-like names, m2m names) for query optimisation."""
    fk = [f.name for f in fields if isinstance(f, (models.ForeignKey, models.OneToOneField))]
    m2m = [f.name for f in fields if isinstance(f, models.ManyToManyField)]
    return fk, m2m


def scalar_and_fk_fields(model: type[models.Model]) -> list[models.Field]:
    """Concrete local fields (scalars + FK), **excluding** many-to-many. For the
    list and relation-option rows, which must never materialize a row's whole
    M2M set (that's an unbounded, per-row load)."""
    return list(model._meta.concrete_fields)


def list_row_fields(model: type[models.Model], list_display) -> list[models.Field]:
    """Fields serialized for a list row: every scalar/FK, plus only the M2M
    fields that are actually shown as a column (those get capped on serialize)."""
    display = set(list_display or [])
    return [
        *model._meta.concrete_fields,
        *[f for f in model._meta.many_to_many if f.name in display],
    ]


# --- read ------------------------------------------------------------------


def _serialize_value(field: models.Field, instance: models.Model, m2m_cap: int | None = None) -> Any:
    if isinstance(field, models.ManyToManyField):
        manager = getattr(instance, field.name)
        # In lists, cap the labels (the field is prefetched, so this uses the
        # cache) so a huge M2M can't bloat the row; append a "+N more" marker.
        # Detail uses no cap (the form needs every selected value).
        if m2m_cap is not None:
            objs = list(manager.all())
            capped = [{"id": o.pk, "label": str(o)} for o in objs[:m2m_cap]]
            if len(objs) > m2m_cap:
                capped.append({"id": None, "label": f"+{len(objs) - m2m_cap} more"})
            return capped
        return [{"id": obj.pk, "label": str(obj)} for obj in manager.all()]
    if isinstance(field, (models.ForeignKey, models.OneToOneField)):
        related = getattr(instance, field.name, None)
        return None if related is None else {"id": related.pk, "label": str(related)}

    value = field.value_from_object(instance)
    if value is None:
        return None
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    return value


def serialize_instance(
    instance: models.Model,
    fields: list[models.Field],
    admin: ModelAdmin | None = None,
    m2m_cap: int | None = None,
) -> dict[str, Any]:
    # ``__str__`` carries the human label (the model's ``__str__`` or the
    # admin's ``display()``), so relation pickers can show it without a real
    # field. The key can never collide with a concrete field name.
    label = admin.display(instance) if admin is not None else str(instance)
    data: dict[str, Any] = {"pk": instance.pk, "__str__": label}
    for field in fields:
        data[field.name] = _serialize_value(field, instance, m2m_cap)
    return data


# Max M2M labels rendered per list cell before a "+N more" marker.
LIST_M2M_CAP = 20


def serialize_list_row(instance: models.Model, model, admin, list_display) -> dict[str, Any]:
    """A list row: scalars + FK + only the M2M shown as columns (capped). Never
    loads a row's non-displayed (or unbounded) M2M sets."""
    return serialize_instance(instance, list_row_fields(model, list_display), admin, LIST_M2M_CAP)


def serialize_option(instance: models.Model, model, admin) -> dict[str, Any]:
    """A relation-picker option: scalars + FK only (the label comes from
    ``__str__`` or a scalar ``display_field``), never M2M."""
    return serialize_instance(instance, scalar_and_fk_fields(model), admin)


# --- write -----------------------------------------------------------------


def _extract_id(raw: Any) -> Any:
    if isinstance(raw, dict):
        return raw.get("id")
    return raw


def apply_data(
    instance: models.Model,
    data: dict[str, Any],
    model: type[models.Model],
    admin: ModelAdmin,
) -> dict[models.ManyToManyField, list[Any]]:
    """Apply ``data`` onto ``instance`` for the editable fields present.

    Returns the M2M assignments to apply AFTER the instance is saved (M2M
    relations require a pk first).
    """
    m2m: dict[models.ManyToManyField, list[Any]] = {}
    for field in editable_fields(model, admin):
        if field.name not in data:
            continue
        raw = data[field.name]
        if isinstance(field, models.ManyToManyField):
            m2m[field] = [_extract_id(item) for item in (raw or [])]
        elif isinstance(field, (models.ForeignKey, models.OneToOneField)):
            setattr(instance, field.attname, _extract_id(raw))
        else:
            setattr(instance, field.name, raw)
    return m2m
