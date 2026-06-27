"""ModelAdmin.description is surfaced in the model schema (shown under the title)."""

import pytest
from django.contrib.auth.models import User
from django.test import Client


@pytest.fixture
def admin_client(db):
    user = User.objects.create_user("root", password="x", is_superuser=True)
    client = Client()
    client.force_login(user)
    return client


def test_description_in_schema(admin_client):
    schema = admin_client.get("/theia/api/schema/sampleapp.stock/").json()
    assert schema["description"] == "Stock items held in a house."


def test_description_defaults_to_empty(admin_client):
    # House admin sets no description -> empty string (never missing).
    schema = admin_client.get("/theia/api/schema/sampleapp.house/").json()
    assert schema["description"] == ""
