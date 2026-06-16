"""Pluggable batch list serialization via a swappable *list provider*.

The generic adapter serializes a list page one instance at a time, paying
Django's per-instance/per-field cost on every row. When a model's rows can be
produced entirely from column-projected queries — every label is a DB-expressible
column, not a Python ``__str__`` — the whole page can be serialized at once by an
external *list provider*.

theia core does NOT depend on any provider library. It only:

1. decides eligibility and builds a backend-agnostic :class:`FieldPlan`, and
2. delegates serialization to a provider configured by the host::

       THEIA_NG = {"LIST_PROVIDER": "fastberry.list_provider.ListProvider"}

   The dotted path must resolve to a class with a
   ``serialize_page(plan, source) -> list[dict]`` method (instantiated once).
   The provider is the swap point — anyone can write one (raw ``.values()``,
   a SQL view, an ORM-agnostic store, …). See :class:`ListProvider` and
   ``docs/list_provider.md``.

When no provider is configured (or it can't be imported), there is no fast path
and the generic per-instance adapter is used — output is never affected.

A model is **fast-eligible** only when:

- it is not delegating to a DRF ``serializer_class``;
- its ``ModelAdmin.display_field`` is set to a concrete scalar field (so the row
  label ``__str__`` is a projectable column, not ``str(instance)``);
- every concrete forward FK's target model is registered with a ``display_field``
  scalar (so each ``{"id","label"}`` label is projectable);
- every *displayed* M2M's target likewise has a ``display_field`` scalar;
- ``list_display`` has no computed columns (admin methods, ``a__b`` lookups, or
  model properties) — those need a real instance.

Provider output is reshaped here into theia's exact list-row contract::

    {"pk", "__str__", <scalar>: value, <fk>: {"id","label"} | None,
     <displayed m2m>: [ {"id","label"}, ..., {"id": None, "label": "+N more"} ]}
"""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

from django.conf import settings
from django.core.exceptions import FieldDoesNotExist
from django.db import models
from django.utils.module_loading import import_string

from theia_ng.api.serialization import LIST_M2M_CAP
from theia_ng.registry import site

if TYPE_CHECKING:
    from theia_ng.options import ModelAdmin


@dataclass
class FieldPlan:
    """Backend-agnostic description of a fast-eligible model's list rows."""

    model: type[models.Model]
    pk_name: str
    display_field: str
    scalar_fields: list[str] = field(default_factory=list)
    # (attr, label_field on the related model)
    fk_labels: list[tuple[str, str]] = field(default_factory=list)
    # (attr, label_field on the related model, cap)
    m2m_labels: list[tuple[str, str, int | None]] = field(default_factory=list)


class ListProvider(Protocol):
    """The interface a ``THEIA_NG['LIST_PROVIDER']`` class must satisfy.

    A provider turns a :class:`FieldPlan` + a queryset (or sliced queryset) into a
    list of dicts keyed by field name — scalars verbatim, decimals stringified,
    forward FKs as ``{"id","label"}`` (None when the FK is null), displayed M2M as
    a capped ``[{"id","label"}, …]`` list. theia adds the ``pk``/``__str__`` keys
    and final JSON coercion afterwards, so a provider only resolves field values.

    Write your own to back the fast path with anything (raw ``.values()``, a
    materialized view, a non-Django store): a class with this one method, pointed
    at by the ``LIST_PROVIDER`` dotted path. It is instantiated once. See
    ``docs/list_provider.md``.
    """

    def serialize_page(self, plan: FieldPlan, source: Any) -> list[dict[str, Any]]: ...


class _Compiled:
    """A built plan + the provider that serializes it, cached per model."""

    __slots__ = ("plan", "provider")

    def __init__(self, plan: FieldPlan, provider: ListProvider):
        self.plan = plan
        self.provider = provider


# (model, columns) -> compiled holder, or None when ineligible / no provider.
_CACHE: dict[tuple, _Compiled | None] = {}
# resolved provider instance (or False once we've found there is none).
_PROVIDER: ListProvider | None | bool = False


def reset_caches() -> None:
    """Forget the resolved provider and per-model plans (tests / settings change)."""
    global _PROVIDER
    _PROVIDER = False
    _CACHE.clear()


def _get_provider() -> ListProvider | None:
    global _PROVIDER
    if _PROVIDER is not False:
        return _PROVIDER  # cached (instance or None)
    _PROVIDER = None
    conf = getattr(settings, "THEIA_NG", {}) or {}
    path = conf.get("LIST_PROVIDER")
    if path:
        try:
            _PROVIDER = import_string(path)()
        except (ImportError, TypeError, ValueError):
            _PROVIDER = None  # misconfigured / not installed -> no fast path
    return _PROVIDER


def _scalar_display_field(model: type[models.Model], admin: Any) -> str | None:
    """The model's ``display_field`` if it names a concrete scalar field, else None."""
    df = getattr(admin, "display_field", None)
    if not df:
        return None
    try:
        f = model._meta.get_field(df)
    except FieldDoesNotExist:
        return None
    if not getattr(f, "concrete", False) or f.is_relation:
        return None
    return df


def _target_label_field(related_model: type[models.Model]) -> str | None:
    """The label field to project for a relation target: its registered admin's
    ``display_field`` (a concrete scalar), or None if not DB-expressible."""
    key = f"{related_model._meta.app_label}.{related_model._meta.model_name}"
    resolved = site.get_model(key)
    if resolved is None:
        return None
    return _scalar_display_field(related_model, resolved[1])


def build_fast_schema(
    model: type[models.Model], admin: ModelAdmin, columns=None
) -> _Compiled | None:
    """Return a cached compiled holder for the model + shown columns, or None if
    not fast-eligible. ``columns`` defaults to the admin's ``list_display``."""
    cols = tuple(columns) if columns is not None else tuple(admin.list_display)
    key = (model, cols)
    if key in _CACHE:
        return _CACHE[key]
    compiled = _try_build(model, admin, cols)
    _CACHE[key] = compiled
    return compiled


def build_plan(model: type[models.Model], admin: ModelAdmin, columns=None) -> FieldPlan | None:
    """The backend-agnostic plan for a model's list rows, scoped to the shown
    ``columns`` (defaults to ``list_display``), or None if not eligible.

    Provider-independent — exposed for testing and tooling."""
    if getattr(admin, "serializer_class", None) is not None:
        return None

    display_field = _scalar_display_field(model, admin)
    if display_field is None:
        return None  # row label would be a Python __str__ -> not projectable

    meta = model._meta
    cols = list(columns) if columns is not None else list(admin.list_display)
    col_set = set(cols)

    # shown columns must be real, projectable fields (no computed/relation-span).
    for name in cols:
        if callable(getattr(admin, name, None)):
            return None  # @display / admin method -> needs an instance
        if "__" in name:
            return None  # relation-spanning lookup -> generic path
        try:
            meta.get_field(name)
        except FieldDoesNotExist:
            return None  # model property / method / attribute -> needs an instance

    plan = FieldPlan(model=model, pk_name=meta.pk.name, display_field=display_field)

    # The pk and the display_field column are always needed (row key + __str__);
    # otherwise only the shown columns are serialized.
    always = {meta.pk.name, display_field}
    for f in meta.concrete_fields:
        if not (f.name in col_set or f.name in always):
            continue
        if isinstance(f, (models.ForeignKey, models.OneToOneField)):
            label = _target_label_field(f.related_model)
            if label is None:
                return None  # FK label not DB-expressible -> generic path
            plan.fk_labels.append((f.name, label))
        else:
            plan.scalar_fields.append(f.name)

    # Only the M2M shown as a column appears in list rows (capped).
    for f in meta.many_to_many:
        if f.name not in col_set:
            continue
        label = _target_label_field(f.related_model)
        if label is None:
            return None
        plan.m2m_labels.append((f.name, label, LIST_M2M_CAP))

    return plan


def _try_build(model: type[models.Model], admin: ModelAdmin, columns=None) -> _Compiled | None:
    provider = _get_provider()
    if provider is None:
        return None
    plan = build_plan(model, admin, columns)
    if plan is None:
        return None
    return _Compiled(plan, provider)


def serialize_page(compiled: _Compiled, source) -> list[dict[str, Any]]:
    """Serialize a list page (queryset / sliced queryset) into theia list rows."""
    plan = compiled.plan
    rows = compiled.provider.serialize_page(plan, source)
    df = plan.display_field
    scalar_names = plan.scalar_fields
    for row in rows:
        row["pk"] = row.get(plan.pk_name)
        label = row.get(df)
        # mirror ModelAdmin.display(): str(value or "")
        row["__str__"] = str(label or "")
        # mirror serialize_instance scalar coercion (Decimal already stringified by
        # the provider); relation {id,label} ids are left as-is, like the generic
        # adapter, and stringified by the JSON encoder.
        for k in scalar_names:
            v = row.get(k)
            if isinstance(v, (datetime.datetime, datetime.date, datetime.time)):
                row[k] = v.isoformat()
            elif isinstance(v, uuid.UUID):
                row[k] = str(v)
    return rows
