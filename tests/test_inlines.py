"""Inlines: child rows described in the IR, read on detail, and saved on the parent."""

import json

import pytest
from django.contrib.auth.models import User
from django.test import Client

from tests.testproject.sampleapp.models import Category, Stock

CAT_SCHEMA = "/theia/api/schema/sampleapp.category/"
CAT_LIST = "/theia/api/data/sampleapp.category/"
CAT_DETAIL = "/theia/api/data/sampleapp.category/{pk}/"


@pytest.fixture
def admin_client(db):
    user = User.objects.create_user("root", password="x", is_superuser=True)
    client = Client()
    client.force_login(user)
    return client


def _patch(client, pk, body):
    return client.patch(CAT_DETAIL.format(pk=pk), data=json.dumps(body), content_type="application/json")


def test_inline_descriptor_in_schema(admin_client):
    inlines = admin_client.get(CAT_SCHEMA).json()["inlines"]
    assert len(inlines) == 1
    inl = inlines[0]
    assert inl["key"] == "sampleapp.stock"
    assert inl["model"] == "sampleapp.stock"
    assert inl["fk_field"] == "category"
    assert inl["style"] == "tabular"
    assert inl["can_delete"] is True
    names = [f["name"] for f in inl["fields"]]
    assert names == ["name", "quantity", "status", "is_active"]
    assert "category" not in names  # parent FK is excluded


def test_detail_includes_existing_child_rows(admin_client):
    cat = Category.objects.create(name="Drinks")
    Stock.objects.create(name="Cola", category=cat, quantity=5)
    Stock.objects.create(name="Water", category=cat, quantity=3)
    rep = admin_client.get(CAT_DETAIL.format(pk=cat.pk)).json()
    rows = rep["inlines"]["sampleapp.stock"]
    assert {r["name"] for r in rows} == {"Cola", "Water"}
    assert all("pk" in r for r in rows)


def test_create_parent_with_inline_rows(admin_client):
    body = {
        "name": "Snacks",
        "inlines": {"sampleapp.stock": [
            {"name": "Chips", "quantity": "2"},
            {"name": "Nuts", "quantity": "1"},
        ]},
    }
    resp = admin_client.post(CAT_LIST, data=json.dumps(body), content_type="application/json")
    assert resp.status_code == 201, resp.content
    cat = Category.objects.get(name="Snacks")
    assert {s.name for s in cat.stocks.all()} == {"Chips", "Nuts"}


def test_update_adds_updates_and_deletes_rows(admin_client):
    cat = Category.objects.create(name="Drinks")
    keep = Stock.objects.create(name="Cola", category=cat, quantity=5)
    drop = Stock.objects.create(name="Old", category=cat, quantity=1)
    body = {
        "inlines": {"sampleapp.stock": [
            {"pk": keep.pk, "name": "Cola Zero", "quantity": "6"},  # update
            {"pk": drop.pk, "_delete": True},                        # delete
            {"name": "Sprite", "quantity": "4"},                     # create
        ]},
    }
    resp = _patch(admin_client, cat.pk, body)
    assert resp.status_code == 200, resp.content
    keep.refresh_from_db()
    assert keep.name == "Cola Zero" and str(keep.quantity) == "6.00"
    assert not Stock.objects.filter(pk=drop.pk).exists()
    assert cat.stocks.filter(name="Sprite").exists()
    # parent FK is forced on the new row
    assert Stock.objects.get(name="Sprite").category_id == cat.pk


def test_inline_validation_error_rolls_back(admin_client):
    cat = Category.objects.create(name="Drinks")
    # A child row missing the required `name` -> full_clean fails -> 400, nothing saved.
    body = {"inlines": {"sampleapp.stock": [{"quantity": "2"}]}}
    resp = _patch(admin_client, cat.pk, body)
    assert resp.status_code == 400
    assert "inlines" in resp.json().get("errors", {})
    assert cat.stocks.count() == 0


def test_delete_flag_ignores_foreign_rows(admin_client):
    """A `_delete` only affects rows that actually belong to this parent."""
    cat = Category.objects.create(name="Drinks")
    other = Category.objects.create(name="Food")
    foreign = Stock.objects.create(name="NotMine", category=other, quantity=1)
    body = {"inlines": {"sampleapp.stock": [{"pk": foreign.pk, "_delete": True}]}}
    resp = _patch(admin_client, cat.pk, body)
    assert resp.status_code == 200
    assert Stock.objects.filter(pk=foreign.pk).exists()  # untouched
