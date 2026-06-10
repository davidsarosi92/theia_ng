"""Data adapter interface + the common validation error.

A ``DataAdapter`` abstracts the three data operations the CRUD views need, so
the generic ORM path and an optional DRF-delegating path are interchangeable.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from django.db.models import Model, QuerySet


class AdapterValidationError(Exception):
    """Uniform validation error raised by adapters.

    ``errors`` is a ``{field_name: [messages]}`` dict (``__all__`` for
    non-field errors), mirroring Django's ``ValidationError.message_dict`` and
    DRF's ``ValidationError.detail``.
    """

    def __init__(self, errors: dict[str, Any]) -> None:
        self.errors = errors
        super().__init__(str(errors))


class DataAdapter:
    """Interface. Concrete adapters: GenericAdapter, DRFAdapter."""

    def get_queryset(self) -> QuerySet:
        raise NotImplementedError

    def to_representation(self, instance: Model) -> dict[str, Any]:
        raise NotImplementedError

    def save(self, instance: Model, data: dict[str, Any], partial: bool = False) -> Model:
        """Validate ``data`` and persist. ``instance`` is unsaved for create.

        Raises ``AdapterValidationError`` on validation failure.
        """
        raise NotImplementedError
