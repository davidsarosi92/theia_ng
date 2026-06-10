"""Optional OpenAPI enrichment.

Per the design, OpenAPI is a THIN, optional enrichment layer — the Django
introspection is the backbone. Given an OpenAPI document (a plain dict, e.g.
produced by drf-spectacular) and a component name, this merges extra hints
(descriptions, enums, formats, required flags) into already-built IR field
specs. It never replaces the model-derived specs.

Works on a plain dict, so it needs no OpenAPI library. If drf-spectacular is
installed, ``generate_spectacular_schema`` can produce the document.
"""

from __future__ import annotations

from typing import Any


def enrich_fields_from_openapi(
    fields: list[dict[str, Any]],
    openapi_schema: dict[str, Any],
    component: str | None,
) -> None:
    """Merge OpenAPI component hints into IR ``fields`` in place."""
    if not component:
        return
    schemas = (openapi_schema.get("components") or {}).get("schemas") or {}
    comp = schemas.get(component)
    if not comp:
        return

    props: dict[str, Any] = comp.get("properties") or {}
    required = set(comp.get("required") or [])
    by_name = {f["name"]: f for f in fields}

    for name, prop in props.items():
        spec = by_name.get(name)
        if spec is None:
            continue
        if prop.get("description") and not spec.get("help_text"):
            spec["help_text"] = prop["description"]
        if prop.get("enum") and not spec.get("choices"):
            spec["choices"] = [{"value": v, "label": str(v)} for v in prop["enum"]]
        if name in required:
            spec["required"] = True
        # A format hint (e.g. "uri", "email", "date-time") a plugin/widget can use.
        if prop.get("format") and not spec.get("widget"):
            spec["widget"] = prop["format"]


def generate_spectacular_schema() -> dict[str, Any]:
    """Build an OpenAPI document via drf-spectacular, if installed."""
    from drf_spectacular.generators import SchemaGenerator  # lazy, optional

    return SchemaGenerator().get_schema(request=None, public=True)
