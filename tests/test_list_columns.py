"""List columns: the server-side allowlist, and each user's own column set."""

import json

import pytest
from django.contrib.auth.models import Permission, User
from django.test import Client

from tests.testproject.sampleapp.models import Category, Stock

LIST = "/theia/api/data/sampleapp.stock/"
SCHEMA = "/theia/api/schema/sampleapp.stock/"
SETTINGS = "/theia/api/settings/"


@pytest.fixture
def viewer(db):
    """May see stocks, may not delete them."""
    user = User.objects.create_user("viewer", password="x")
    user.user_permissions.add(
        Permission.objects.get(codename="access", content_type__app_label="theia_ng"),
        Permission.objects.get(codename="view_stock"),
    )
    client = Client()
    client.force_login(user)
    return client


@pytest.fixture
def stocks(db):
    cat = Category.objects.create(name="Drinks")
    return [
        Stock.objects.create(name="beer", category=cat, notes="n1"),
        Stock.objects.create(name="wine", category=cat, notes="n2"),
    ]


def _patch(client, body):
    return client.patch(SETTINGS, data=json.dumps(body), content_type="application/json")


# --- the allowlist -----------------------------------------------------------


def test_columns_cannot_call_model_methods(viewer, stocks):
    # Regression: a column name was resolved with getattr and called, so this GET
    # used to run obj.delete() on every listed row, without delete permission.
    resp = viewer.get(LIST, {"columns": "name,delete,save,refresh_from_db"})
    assert resp.status_code == 200
    assert Stock.objects.count() == 2
    row = resp.json()["results"][0]
    assert "delete" not in row and "save" not in row
    assert row["name"] == "beer"


def test_columns_cannot_call_admin_methods_not_declared(viewer, stocks):
    resp = viewer.get(LIST, {"columns": "name,has_delete_permission,get_queryset"})
    row = resp.json()["results"][0]
    assert "has_delete_permission" not in row and "get_queryset" not in row


def test_only_unknown_columns_falls_back_to_list_display(viewer, stocks):
    row = viewer.get(LIST, {"columns": "delete"}).json()["results"][0]
    assert {"name", "category", "house__name", "quantity", "is_active"} <= set(row)


def test_model_fields_and_optional_columns_are_allowed(viewer, stocks):
    row = viewer.get(LIST, {"columns": "notes,category__name,shout"}).json()["results"][0]
    assert row["notes"] == "n1"
    assert row["category__name"] == "Drinks"
    assert row["shout"] == "BEER"


def test_ordering_by_unlisted_lookup_is_ignored(viewer, stocks):
    # A lookup outside the pool would let a viewer probe hidden related values.
    resp = viewer.get(LIST, {"ordering": "-category__stocks__notes"})
    assert resp.status_code == 200
    assert [r["name"] for r in resp.json()["results"]] == ["beer", "wine"]  # admin ordering


def test_ordering_by_pool_column_still_works(viewer, stocks):
    resp = viewer.get(LIST, {"ordering": "-name"})
    assert [r["name"] for r in resp.json()["results"]] == ["wine", "beer"]


def test_ordering_drops_only_the_bad_term(viewer, stocks):
    resp = viewer.get(LIST, {"ordering": "delete,-notes"})
    assert [r["name"] for r in resp.json()["results"]] == ["wine", "beer"]


# --- the IR ------------------------------------------------------------------


def test_schema_advertises_the_pool(viewer):
    lst = viewer.get(SCHEMA).json()["list"]
    assert lst["customizable"] is True
    # list_display first (the default), then the optional ones, then fields.
    assert lst["available"][:7] == [
        "name", "category", "house__name", "quantity", "is_active", "category__name", "shout",
    ]
    assert "notes" in lst["available"]
    assert lst["labels"]["shout"] == "Shout"
    assert lst["labels"]["notes"] == "Notes"


def test_optional_lookup_gets_a_field_descriptor(viewer):
    names = {f["name"] for f in viewer.get(SCHEMA).json()["fields"]}
    assert "category__name" in names  # so the SPA can label and sort it


# --- per-user column sets ----------------------------------------------------


def test_user_columns_roundtrip_and_merge_per_model(viewer):
    assert viewer.get(SETTINGS).json()["list_columns"] == {}
    body = _patch(viewer, {"list_columns": {"sampleapp.stock": ["notes", "name"]}}).json()
    assert body["list_columns"] == {"sampleapp.stock": ["notes", "name"]}
    body = _patch(viewer, {"list_columns": {"sampleapp.house": ["name"]}}).json()
    assert body["list_columns"] == {
        "sampleapp.stock": ["notes", "name"],
        "sampleapp.house": ["name"],
    }


def test_user_columns_reset_with_null_or_empty(viewer):
    _patch(viewer, {"list_columns": {"sampleapp.stock": ["name"], "sampleapp.house": ["name"]}})
    body = _patch(viewer, {"list_columns": {"sampleapp.stock": None, "sampleapp.house": []}}).json()
    assert body["list_columns"] == {}


def test_user_columns_are_limited_to_the_pool(viewer):
    body = _patch(
        viewer,
        {"list_columns": {
            "sampleapp.stock": ["name", "delete", "name", "shout"],
            "nope.missing": ["x"],
        }},
    ).json()
    assert body["list_columns"] == {"sampleapp.stock": ["name", "shout"]}


def test_user_columns_respect_list_customizable(viewer):
    body = _patch(viewer, {"list_columns": {"sampleapp.space": ["name"]}}).json()
    assert body["list_columns"] == {}


@pytest.mark.parametrize("bad", [["name"], {"sampleapp.stock": "name"}, {"sampleapp.stock": [1]}])
def test_user_columns_reject_malformed(viewer, bad):
    assert _patch(viewer, {"list_columns": bad}).status_code == 400
