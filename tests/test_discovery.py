"""Opt-in discovery of django admin.py registrations (compatible options only)."""

import pytest
from django.contrib.auth.models import User
from django.test import RequestFactory, override_settings

from theia_ng.discovery import discover_django_admins
from theia_ng.introspection import build_model_detail
from theia_ng.registry import site
from tests.testproject.sampleapp.models import Bundle


@pytest.fixture
def discovered(db):
    """Run discovery with the flag on, then restore the global registry (discovery
    also picks up auth's User/Group, so unregister everything it added)."""
    assert not site.is_registered(Bundle)
    before = set(site.registry.keys())
    with override_settings(THEIA_NG={"DISCOVER_ADMIN_FILES": True}):
        discover_django_admins(site)
    try:
        yield site.get_model("sampleapp.bundle")
    finally:
        for model in list(site.registry.keys()):
            if model not in before:
                site.unregister(model)


def test_disabled_by_default(db):
    # No flag -> nothing discovered, Bundle stays unregistered.
    assert discover_django_admins(site) == 0
    assert not site.is_registered(Bundle)


def test_discovers_only_compatible_options(discovered):
    model, admin = discovered
    assert model is Bundle
    # method column + __str__ default dropped; real fields kept
    assert admin.list_display == ["name", "id"]
    # SimpleListFilter dropped; plain field filter kept
    assert admin.list_filter == ["name"]
    assert admin.search_fields == ["name"]
    assert admin.ordering == ["name"]
    # method readonly dropped; real field kept
    assert admin.readonly_fields == ["id"]
    assert admin.raw_id_fields == ["stocks"]
    # actions are NOT portable (different signature) -> not copied
    assert admin.actions == []


def test_discovered_model_builds_ir(discovered):
    model, admin = discovered
    req = RequestFactory().get("/")
    req.user = User.objects.create_user("root", password="x", is_superuser=True)
    detail = build_model_detail(model, admin, req)
    assert detail["list"]["display"] == ["name", "id"]
    assert {f["name"] for f in detail["fields"]} >= {"name", "stocks"}


def test_explicit_theia_registration_wins(db):
    """If a model is registered via theia.py, discovery must not override it."""
    import theia_ng

    @theia_ng.register(Bundle)
    class BundleTheia(theia_ng.ModelAdmin):
        search_fields = ["name"]

    before = set(site.registry.keys())
    try:
        with override_settings(THEIA_NG={"DISCOVER_ADMIN_FILES": True}):
            discover_django_admins(site)
        _model, admin = site.get_model("sampleapp.bundle")
        assert isinstance(admin, BundleTheia)  # the explicit one, untouched
    finally:
        for model in list(site.registry.keys()):
            if model not in before or model is Bundle:
                site.unregister(model)
