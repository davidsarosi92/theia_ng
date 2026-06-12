"""Per-user favorites endpoint."""

import json

import pytest
from django.contrib.auth.models import User
from django.test import Client

URL = "/theia/api/favorites/"


@pytest.fixture
def admin_client(db):
    user = User.objects.create_user("root", password="x", is_superuser=True)
    client = Client()
    client.force_login(user)
    return client


def _put(client, favorites):
    return client.put(URL, data=json.dumps({"favorites": favorites}), content_type="application/json")


def test_starts_empty(admin_client):
    assert admin_client.get(URL).json() == {"favorites": []}


def test_put_then_get_roundtrips(admin_client):
    resp = _put(admin_client, ["sampleapp.stock", "sampleapp.house"])
    assert resp.status_code == 200
    assert resp.json() == {"favorites": ["sampleapp.stock", "sampleapp.house"]}
    assert admin_client.get(URL).json()["favorites"] == ["sampleapp.stock", "sampleapp.house"]


def test_put_replaces_and_dedupes_preserving_order(admin_client):
    _put(admin_client, ["sampleapp.stock"])
    resp = _put(admin_client, ["sampleapp.house", "sampleapp.stock", "sampleapp.house"])
    assert resp.json()["favorites"] == ["sampleapp.house", "sampleapp.stock"]


def test_put_rejects_non_list(admin_client):
    resp = admin_client.put(URL, data=json.dumps({"favorites": "nope"}), content_type="application/json")
    assert resp.status_code == 400


def test_is_per_user(db):
    a = User.objects.create_user("a", password="x", is_superuser=True)
    b = User.objects.create_user("b", password="x", is_superuser=True)
    ca, cb = Client(), Client()
    ca.force_login(a)
    cb.force_login(b)
    _put(ca, ["sampleapp.stock"])
    assert cb.get(URL).json()["favorites"] == []


def test_requires_access(db):
    # Anonymous (no session) is forbidden.
    assert Client().get(URL).status_code == 403
