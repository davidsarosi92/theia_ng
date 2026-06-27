"""Per-user UI settings endpoint (language, timezone, theme, nav order)."""

import json

import pytest
from django.contrib.auth.models import User
from django.test import Client

URL = "/theia/api/settings/"


@pytest.fixture
def admin_client(db):
    user = User.objects.create_user("root", password="x", is_superuser=True)
    client = Client()
    client.force_login(user)
    return client


def _patch(client, body):
    return client.patch(URL, data=json.dumps(body), content_type="application/json")


def test_get_returns_defaults_with_languages(admin_client):
    body = admin_client.get(URL).json()
    # Defaults sourced from Django; concrete values always present.
    assert body["theme"] == "auto"
    assert body["button_style"] == "label"
    assert body["nav_order"] == []
    assert body["language"]  # non-empty (get_language()/LANGUAGE_CODE)
    assert body["timezone"]  # non-empty (active timezone)
    codes = {entry["code"] for entry in body["available_languages"]}
    assert {"en", "hu", "de"} <= codes


def test_patch_persists_and_roundtrips(admin_client):
    resp = _patch(
        admin_client,
        {
            "language": "hu",
            "theme": "dark",
            "nav_app_order": ["goods", "structure"],
            "nav_order": ["a.b", "c.d"],
        },
    )
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["language"] == "hu"
    assert body["theme"] == "dark"
    assert body["nav_app_order"] == ["goods", "structure"]
    assert body["nav_order"] == ["a.b", "c.d"]
    # persisted
    assert admin_client.get(URL).json()["theme"] == "dark"


def test_get_defaults_include_empty_nav_orders(admin_client):
    body = admin_client.get(URL).json()
    assert body["nav_app_order"] == []
    assert body["nav_order"] == []


def test_patch_partial_keeps_other_values(admin_client):
    _patch(admin_client, {"theme": "light"})
    _patch(admin_client, {"language": "de"})
    body = admin_client.get(URL).json()
    assert body["theme"] == "light"
    assert body["language"] == "de"


def test_patch_rejects_unsupported_language(admin_client):
    assert _patch(admin_client, {"language": "xx"}).status_code == 400


def test_patch_rejects_unsupported_theme(admin_client):
    assert _patch(admin_client, {"theme": "neon"}).status_code == 400


def test_button_style_roundtrips_and_validates(admin_client):
    body = _patch(admin_client, {"button_style": "both"}).json()
    assert body["button_style"] == "both"
    assert admin_client.get(URL).json()["button_style"] == "both"
    assert _patch(admin_client, {"button_style": "huge"}).status_code == 400


def test_nav_order_dedupes_preserving_order(admin_client):
    body = _patch(admin_client, {"nav_order": ["a.b", "c.d", "a.b"]}).json()
    assert body["nav_order"] == ["a.b", "c.d"]


def test_is_per_user(db):
    a = User.objects.create_user("a", password="x", is_superuser=True)
    b = User.objects.create_user("b", password="x", is_superuser=True)
    ca, cb = Client(), Client()
    ca.force_login(a)
    cb.force_login(b)
    _patch(ca, {"theme": "dark"})
    assert cb.get(URL).json()["theme"] == "auto"


def test_requires_access(db):
    assert Client().get(URL).status_code == 403
