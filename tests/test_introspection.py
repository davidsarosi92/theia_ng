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


def test_registry_choice_field_renders_as_model_multiselect(admin_request):
    from theia_ng.models import MenuView

    detail = build_model_detail(MenuView, site.registry[MenuView], admin_request)
    field = next(f for f in detail["fields"] if f["name"] == "model_keys")
    assert field["widget"] == "multiselect"
    values = {c["value"] for c in field["choices"]}
    assert "sampleapp.stock" in values  # choices are the registered model keys


def test_registry_views_intersected_with_permitted_models(admin_request):
    from theia_ng.models import MenuView

    MenuView.objects.create(
        name="Management",
        model_keys=["sampleapp.stock", "nope.missing"],
        model_fields={"sampleapp.stock": ["name", "category"], "nope.missing": ["x"]},
    )
    payload = build_registry(site, admin_request)
    views = {v["name"]: v for v in payload["views"]}
    assert "Management" in views
    # only keys the user can actually see survive (permissions win)
    assert views["Management"]["models"] == ["sampleapp.stock"]
    # per-model field lists, intersected to accessible models too
    assert views["Management"]["fields"] == {"sampleapp.stock": ["name", "category"]}


def test_custom_list_filter_in_ir():
    import theia_ng
    from theia_ng.introspection.builder import _model_structure

    class ActiveFilter(theia_ng.ListFilter):
        title = "Active?"
        parameter_name = "active_only"

        def lookups(self, request):
            return [("yes", "Yes"), ("no", "No")]

        def queryset(self, request, queryset, value):
            return queryset

    class A(theia_ng.ModelAdmin):
        list_filter = ["is_active", ActiveFilter]

    s = _model_structure(Stock, A(Stock, None))
    assert s["list"]["filters"] == ["is_active"]  # plain field filter
    cf = s["list"]["custom_filters"]
    assert cf == [
        {
            "param": "active_only",
            "label": "Active?",
            "choices": [{"value": "yes", "label": "Yes"}, {"value": "no", "label": "No"}],
        }
    ]


def test_model_field_select_widget(admin_request):
    from theia_ng.models import MenuView

    detail = build_model_detail(MenuView, site.registry[MenuView], admin_request)
    field = next(f for f in detail["fields"] if f["name"] == "model_fields")
    assert field["widget"] == "model_field_select"
    assert field["models_field"] == "model_keys"
    # field_choices: per registered model, its selectable fields
    stock = field["field_choices"]["sampleapp.stock"]
    names = {c["value"] for c in stock["fields"]}
    assert "name" in names and "category" in names
    assert "id" not in names  # auto pk excluded
