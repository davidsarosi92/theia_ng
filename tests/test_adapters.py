"""Tests for the optional DRF / OpenAPI adapters."""

import pytest

from theia_ng.adapters import AdapterValidationError, resolve_adapter
from theia_ng.adapters.drf import DRFAdapter, enrich_fields_from_serializer
from theia_ng.adapters.generic import GenericAdapter
from theia_ng.adapters.openapi import enrich_fields_from_openapi
from theia_ng.introspection.builder import build_model_detail
from theia_ng.options import ModelAdmin
from tests.testproject.sampleapp.models import Category, Stock
from tests.testproject.sampleapp.serializers import StockSerializer


class DRFStockAdmin(ModelAdmin):
    serializer_class = StockSerializer


@pytest.fixture
def category(db):
    return Category.objects.create(name="Drinks")


# --- adapter selection -----------------------------------------------------


def test_resolve_adapter_picks_generic_by_default():
    admin = ModelAdmin(Stock, None)
    assert isinstance(resolve_adapter(Stock, admin), GenericAdapter)


def test_resolve_adapter_picks_drf_when_serializer_set():
    admin = DRFStockAdmin(Stock, None)
    assert isinstance(resolve_adapter(Stock, admin), DRFAdapter)


# --- DRF delegation --------------------------------------------------------


def test_drf_adapter_saves_and_represents(category):
    adapter = DRFAdapter(Stock, DRFStockAdmin(Stock, None))
    instance = adapter.save(Stock(), {"name": "Beer", "category": category.pk, "quantity": "5.00"})
    assert instance.pk is not None

    rep = adapter.to_representation(instance)
    assert rep["name"] == "Beer"
    assert rep["category"] == category.pk  # DRF native shape (bare pk)
    assert rep["pk"] == instance.pk


def test_drf_adapter_enforces_serializer_validation(category):
    adapter = DRFAdapter(Stock, DRFStockAdmin(Stock, None))
    with pytest.raises(AdapterValidationError) as exc:
        adapter.save(Stock(), {"name": "forbidden", "category": category.pk})
    assert "name" in exc.value.errors


# --- IR enrichment ---------------------------------------------------------


def test_serializer_enrichment_marks_readonly_fields():
    fields = [
        {"name": "id", "required": False, "read_only": False, "editable": True, "help_text": ""},
        {"name": "name", "required": False, "read_only": False, "editable": True, "help_text": ""},
    ]
    enrich_fields_from_serializer(fields, StockSerializer)
    by_name = {f["name"]: f for f in fields}
    assert by_name["id"]["read_only"] is True
    assert by_name["id"]["editable"] is False
    assert by_name["name"]["required"] is True


def test_openapi_enrichment_merges_hints():
    fields = [
        {"name": "status", "help_text": "", "widget": None},
        {"name": "notes", "help_text": "", "widget": None},
    ]
    schema = {
        "components": {
            "schemas": {
                "Stock": {
                    "required": ["status"],
                    "properties": {
                        "status": {"enum": ["draft", "active"], "description": "Lifecycle state"},
                        "notes": {"format": "textarea"},
                    },
                }
            }
        }
    }
    enrich_fields_from_openapi(fields, schema, "Stock")
    by_name = {f["name"]: f for f in fields}
    assert by_name["status"]["help_text"] == "Lifecycle state"
    assert by_name["status"]["required"] is True
    assert by_name["status"]["choices"] == [
        {"value": "draft", "label": "draft"},
        {"value": "active", "label": "active"},
    ]
    assert by_name["notes"]["widget"] == "textarea"
