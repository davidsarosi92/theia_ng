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
    # entries carry app grouping info
    stock = next(m for m in payload["models"] if m["key"] == "sampleapp.stock")
    assert stock["app_label"] == "sampleapp"
    assert "app_verbose_name" in stock


def test_readonly_fields_marked_non_editable_in_ir():
    from theia_ng.introspection.builder import _model_structure
    from theia_ng.options import ModelAdmin

    class RoAdmin(ModelAdmin):
        readonly_fields = ["name"]

    structure = _model_structure(Stock, RoAdmin(Stock, None))
    name = next(f for f in structure["fields"] if f["name"] == "name")
    assert name["read_only"] is True
    assert name["editable"] is False
    # A plain editable field is not read_only just because some are.
    quantity = next(f for f in structure["fields"] if f["name"] == "quantity")
    assert quantity["read_only"] is False


def test_exclude_drops_field_from_form():
    from theia_ng.introspection.builder import _model_structure
    from theia_ng.options import ModelAdmin

    class ExAdmin(ModelAdmin):
        exclude = ["name"]

    structure = _model_structure(Stock, ExAdmin(Stock, None))
    name = next(f for f in structure["fields"] if f["name"] == "name")
    # hidden from the form (editable False) but NOT shown read-only
    assert name["editable"] is False
    assert name["read_only"] is False


def test_list_display_labels():
    import theia_ng
    from theia_ng.introspection.builder import _model_structure

    class LabelAdmin(theia_ng.ModelAdmin):
        list_display = ["is_active", "shouty"]

        @theia_ng.display(description="Shouty name")
        def shouty(self, obj):
            return obj.name.upper()

    structure = _model_structure(Stock, LabelAdmin(Stock, None))
    labels = structure["list"]["labels"]
    assert labels["is_active"] == "Is Active"  # field, humanized
    assert labels["shouty"] == "Shouty name"  # computed column, short_description


def test_raw_id_fields_marks_relation_raw():
    from theia_ng.introspection.builder import _model_structure
    from theia_ng.options import ModelAdmin

    class RawAdmin(ModelAdmin):
        raw_id_fields = ["category"]

    structure = _model_structure(Stock, RawAdmin(Stock, None))
    fields = {f["name"]: f for f in structure["fields"]}
    assert fields["category"]["relation"]["raw"] is True
    assert fields["spaces"]["relation"]["raw"] is False


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
    # Category sets display_field explicitly -> that field labels the relation
    assert fields["category"]["relation"]["display_field"] == "name"
    # Space has no display_field -> defaults to the object's __str__
    assert fields["spaces"]["relation"]["display_field"] == "__str__"
    # registered targets get a picker; the flag tells the SPA so
    assert fields["category"]["relation"]["registered"] is True
    # auto-derived verbose_name is title-cased: is_active -> "Is Active"
    assert fields["is_active"]["label"] == "Is Active"
    assert detail["list"]["display"] == ["name", "category", "quantity", "is_active"]

    # static defaults serialized; callable/no-default -> None
    assert fields["is_active"]["default"] is True
    assert fields["status"]["default"] == "draft"
    assert fields["name"]["default"] is None

    # reverse relations (Bundle.stocks -> Stock.bundles) must NOT appear as fields
    assert "bundles" not in fields
