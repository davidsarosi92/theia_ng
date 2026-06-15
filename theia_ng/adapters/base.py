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

    def to_list_representation(self, instance: Model, list_display) -> dict[str, Any]:
        """A lighter row for the list/options endpoint — must not materialize a
        row's whole M2M sets. Defaults to the full representation; the generic
        adapter overrides it to serialize only the displayed columns."""
        return self.to_representation(instance)

    def serialize_list_page(self, source: QuerySet, list_display) -> list[dict[str, Any]] | None:
        """Optional batch fast path: serialize a whole page of list rows at once.

        Return a list of rows (same shape as ``to_list_representation``) to skip
        the per-instance loop, or ``None`` to let the view fall back to it. The
        default has no fast path; ``FastRestAdapter`` overrides it."""
        return None

    def save(self, instance: Model, data: dict[str, Any], partial: bool = False) -> Model:
        """Validate ``data`` and persist. ``instance`` is unsaved for create.

        Raises ``AdapterValidationError`` on validation failure.
        """
        raise NotImplementedError
