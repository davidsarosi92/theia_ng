"""Fieldsets + list_editable IR (form sectioning and inline list editing)."""

import pytest
from django.contrib.auth.models import User
from django.test import Client

SCHEMA = "/theia/api/schema/sampleapp.stock/"


@pytest.fixture
def admin_client(db):
    user = User.objects.create_user("root", password="x", is_superuser=True)
    client = Client()
    client.force_login(user)
    return client


def test_fieldsets_in_schema(admin_client):
    fs = admin_client.get(SCHEMA).json()["fieldsets"]
    assert fs is not None and len(fs) == 2
    first, details = fs
    assert first["title"] is None
    assert first["fields"] == ["name", "category", "quantity"]
    assert first["collapsible"] is False
    assert details["title"] == "Details"
    assert details["fields"] == ["status", "is_active", "notes"]
    assert details["collapsible"] is True
    assert details["description"] == "Optional details."


def test_list_editable_in_schema(admin_client):
    schema = admin_client.get(SCHEMA).json()
    assert schema["list"]["editable"] == ["quantity", "is_active"]


def test_no_fieldsets_is_null(admin_client):
    # Category has no fieldsets configured.
    assert admin_client.get("/theia/api/schema/sampleapp.category/").json()["fieldsets"] is None
