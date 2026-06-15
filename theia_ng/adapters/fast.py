"""Fast list adapter: batch read path via the configured provider, generic write path.

Subclasses :class:`GenericAdapter` so create/update/validation (``save``) and the
detail ``to_representation`` keep their exact ORM semantics. Only the list page
is accelerated, via :func:`theia_ng.api.fast_list.serialize_page` (which delegates
to the host-configured ``FAST_LIST_PROVIDER``) — and only for models that
:func:`theia_ng.api.fast_list.build_fast_schema` deemed eligible (``resolve_adapter``
constructs this adapter solely in that case).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from theia_ng.adapters.generic import GenericAdapter
from theia_ng.api.fast_list import serialize_page

if TYPE_CHECKING:
    from django.db.models import Model, QuerySet

    from theia_ng.options import ModelAdmin


class FastRestAdapter(GenericAdapter):
    def __init__(self, model: type[Model], admin: ModelAdmin, fast_schema) -> None:
        super().__init__(model, admin)
        self._fast = fast_schema

    def serialize_list_page(self, source: QuerySet, list_display) -> list[dict[str, Any]]:
        return serialize_page(self._fast, source)