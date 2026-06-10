"""Optional DRF delegation.

When a ModelAdmin sets ``serializer_class``, data operations defer to that DRF
serializer: it drives (de)serialization, validation and save — so the host
project's existing business logic, validators and permissions baked into the
serializer are respected.

``rest_framework`` is imported lazily inside functions, so the core package
never requires DRF to be installed.

Known limitation: a DRF serializer's relation fields serialize to their native
shape (usually a bare pk), not Theia NG's ``{id, label}`` shape. The frontend
renders scalars fine in lists, but relation edit widgets expect the rich shape;
delegated models may need a serializer that emits ``{id, label}`` or a custom
widget.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from theia_ng.adapters.base import AdapterValidationError, DataAdapter

if TYPE_CHECKING:
    from django.db.models import Model, QuerySet

    from theia_ng.options import ModelAdmin


class DRFAdapter(DataAdapter):
    def __init__(self, model: type[Model], admin: ModelAdmin) -> None:
        self.model = model
        self.admin = admin
        self.serializer_class = admin.serializer_class

    def get_queryset(self) -> QuerySet:
        return self.model._default_manager.all()

    def to_representation(self, instance: Model) -> dict[str, Any]:
        data = dict(self.serializer_class(instance).data)
        data.setdefault("pk", instance.pk)
        return data

    def save(self, instance: Model, data: dict[str, Any], partial: bool = False) -> Model:
        from rest_framework.exceptions import ValidationError as DRFValidationError

        # DRF expects instance=None for create.
        target = instance if getattr(instance, "pk", None) else None
        serializer = self.serializer_class(instance=target, data=data, partial=partial)
        try:
            serializer.is_valid(raise_exception=True)
        except DRFValidationError as exc:
            raise AdapterValidationError(dict(exc.detail)) from exc
        return serializer.save()


def enrich_fields_from_serializer(fields: list[dict[str, Any]], serializer_class: type) -> None:
    """Override IR field flags with the DRF serializer's richer metadata.

    The serializer is the source of truth for required/read-only/help-text when
    a model is DRF-delegated; mutates ``fields`` in place.
    """
    serializer = serializer_class()
    by_name = {f["name"]: f for f in fields}
    for name, drf_field in serializer.fields.items():
        spec = by_name.get(name)
        if spec is None:
            continue
        spec["required"] = bool(drf_field.required)
        spec["read_only"] = bool(drf_field.read_only)
        if drf_field.read_only:
            spec["editable"] = False
        if getattr(drf_field, "help_text", None):
            spec["help_text"] = str(drf_field.help_text)
