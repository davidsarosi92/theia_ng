"""Smoke tests for the IR builder and the type system."""

import pytest
from django.contrib.auth.models import AnonymousUser, Permission, User
from django.test import RequestFactory

from theia_ng.introspection import build_model_detail, build_registry
from theia_ng.introspection.types import FieldType, resolve_field_type
from theia_ng.registry import site
from tests.testproject.sampleapp.models import Category, Stock


@pytest.fixture
def admin_request(db):
    user = User.objects.create_user("admin", password="x", is_superuser=True, is_staff=False)
    req = RequestFactory().get("/theia/api/schema/")
    req.user = user
    return req


def test_resolve_field_type_covers_common_fields():
    fields = {f.name: f for f in Stock._meta.get_fields()}
    assert resolve_field_type(fields["name"]) is FieldType.STRING
    assert resolve_field_type(fields["quantity"]) is FieldType.DECIMAL
    assert resolve_field_type(fields["status"]) is FieldType.CHOICE
    assert resolve_field_type(fields["is_active"]) is FieldType.BOOLEAN
    assert resolve_field_type(fields["notes"]) is FieldType.TEXT
    assert resolve_field_type(fields["category"]) is FieldType.FK


def test_registry_lists_registered_models(admin_request):
    payload = build_registry(site, admin_request)
    keys = {m["key"] for m in payload["models"]}
    assert "sampleapp.stock" in keys
    assert "sampleapp.category" in keys
    assert payload["schema_version"] == "1.0"


def test_model_detail_includes_fields_and_relation(admin_request):
    admin = site.registry[Stock]
    detail = build_model_detail(Stock, admin, admin_request)
    fields = {f["name"]: f for f in detail["fields"]}

    assert fields["status"]["choices"] == [
        {"value": "draft", "label": "Draft"},
        {"value": "active", "label": "Active"},
    ]
    assert fields["category"]["type"] == "fk"
    assert fields["category"]["relation"]["target"] == "sampleapp.category"
    # display_field derived from Category's ModelAdmin (search_fields=['name'])
    assert fields["category"]["relation"]["display_field"] == "name"
    assert detail["list"]["display"] == ["name", "category", "quantity", "is_active"]

    # static defaults serialized; callable/no-default -> None
    assert fields["is_active"]["default"] is True
    assert fields["status"]["default"] == "draft"
    assert fields["name"]["default"] is None

    # reverse relations (Bundle.stocks -> Stock.bundles) must NOT appear as fields
    assert "bundles" not in fields
