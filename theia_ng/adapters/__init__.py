"""Optional delegation adapters.

The core depends only on django.contrib.auth, never on DRF. Adapters let Theia
NG defer to a host project's existing API layer (DRF serializers) or enrich the
IR from an OpenAPI document. They load lazily so importing theia_ng never
requires DRF to be installed.

``resolve_adapter`` picks the data adapter for a model: the DRF adapter when the
ModelAdmin declares ``serializer_class``, otherwise the generic ORM adapter.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from theia_ng.adapters.base import AdapterValidationError, DataAdapter

if TYPE_CHECKING:
    from django.db.models import Model

    from theia_ng.options import ModelAdmin

__all__ = ["AdapterValidationError", "DataAdapter", "resolve_adapter"]


def resolve_adapter(model: type[Model], admin: ModelAdmin) -> DataAdapter:
    if getattr(admin, "serializer_class", None) is not None:
        from theia_ng.adapters.drf import DRFAdapter

        return DRFAdapter(model, admin)

    # Fast list path (fastberry) for models whose rows are fully DB-projectable;
    # falls back to generic when not eligible or fastberry is unavailable.
    from theia_ng.api.fast_list import build_fast_schema

    fast_schema = build_fast_schema(model, admin)
    if fast_schema is not None:
        from theia_ng.adapters.fast import FastRestAdapter

        return FastRestAdapter(model, admin, fast_schema)

    from theia_ng.adapters.generic import GenericAdapter

    return GenericAdapter(model, admin)
