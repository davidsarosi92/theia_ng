"""The default adapter: operates directly on the ORM.

This is the fallback used whenever a model's ModelAdmin does not opt into a
richer adapter (e.g. DRF). It carries the validation + save semantics that used
to live in the CRUD view: ``full_clean()`` inside a transaction, with M2M set
after the instance has a pk.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction

from theia_ng.adapters.base import AdapterValidationError, DataAdapter
from theia_ng.api.serialization import apply_data, serializable_fields, serialize_instance

if TYPE_CHECKING:
    from django.db.models import Model, QuerySet

    from theia_ng.options import ModelAdmin


class GenericAdapter(DataAdapter):
    def __init__(self, model: type[Model], admin: ModelAdmin) -> None:
        self.model = model
        self.admin = admin
        self._fields = serializable_fields(model)

    def get_queryset(self) -> QuerySet:
        return self.model._default_manager.all()

    def to_representation(self, instance: Model) -> dict[str, Any]:
        return serialize_instance(instance, self._fields)

    def save(self, instance: Model, data: dict[str, Any], partial: bool = False) -> Model:
        with transaction.atomic():
            m2m = apply_data(instance, data, self.model, self.admin)
            try:
                instance.full_clean(exclude=[f.name for f in m2m])
            except DjangoValidationError as exc:
                errors = exc.message_dict if hasattr(exc, "error_dict") else {"__all__": exc.messages}
                raise AdapterValidationError(errors) from exc
            instance.save()
            for field, ids in m2m.items():
                getattr(instance, field.name).set(ids)
        return instance
