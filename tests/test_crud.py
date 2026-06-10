"""End-to-end tests for the auto-CRUD endpoints (via the test Client)."""

import json

import pytest
from django.contrib.auth.models import User
from django.test import Client

from tests.testproject.sampleapp.models import Category, Stock

LIST = "/theia/api/data/sampleapp.stock/"
DETAIL = "/theia/api/data/sampleapp.stock/{pk}/"
ACTION = "/theia/api/action/sampleapp.stock/deactivate/"


@pytest.fixture
def category(db):
    return Category.objects.create(name="Drinks")


@pytest.fixture
def admin_client(db):
    user = User.objects.create_user("root", password="x", is_superuser=True)
    client = Client()
    client.force_login(user)
    return client


def test_create_and_retrieve(admin_client, category):
    resp = admin_client.post(
        LIST,
        data=json.dumps({"name": "Beer", "category": category.pk, "quantity": "12.50"}),
        content_type="application/json",
    )
    assert resp.status_code == 201, resp.content
    body = resp.json()
    assert body["name"] == "Beer"
    assert body["category"] == {"id": category.pk, "label": "Drinks"}
    assert body["quantity"] == "12.50"  # Decimal preserved as string

    pk = body["pk"]
    got = admin_client.get(DETAIL.format(pk=pk))
    assert got.status_code == 200
    assert got.json()["name"] == "Beer"


def test_list_with_boolean_filter(admin_client, category):
    Stock.objects.create(name="Beer", category=category, is_active=True)
    Stock.objects.create(name="Wine", category=category, is_active=False)

    # 'is_active' is in StockAdmin.list_filter; boolean string is coerced
    resp = admin_client.get(LIST, {"is_active": "false"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    assert body["results"][0]["name"] == "Wine"


def test_list_with_fk_filter(admin_client, category):
    other = Category.objects.create(name="Food")
    Stock.objects.create(name="Beer", category=category)
    Stock.objects.create(name="Bread", category=other)

    resp = admin_client.get(LIST, {"category": other.pk})
    assert resp.status_code == 200
    assert resp.json()["count"] == 1
    assert resp.json()["results"][0]["name"] == "Bread"


def test_list_ordering(admin_client, category):
    Stock.objects.create(name="Beer", category=category)
    Stock.objects.create(name="Wine", category=category)

    resp = admin_client.get(LIST, {"ordering": "-name"})
    names = [r["name"] for r in resp.json()["results"]]
    assert names == ["Wine", "Beer"]


def test_list_with_search(admin_client, category):
    Stock.objects.create(name="Beer", category=category)
    Stock.objects.create(name="Wine", category=category)

    resp = admin_client.get(LIST, {"search": "bee"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    assert body["results"][0]["name"] == "Beer"


def test_update(admin_client, category):
    stock = Stock.objects.create(name="Beer", category=category, quantity=1)
    resp = admin_client.patch(
        DETAIL.format(pk=stock.pk),
        data=json.dumps({"quantity": "99.00"}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    stock.refresh_from_db()
    assert str(stock.quantity) == "99.00"


def test_delete(admin_client, category):
    stock = Stock.objects.create(name="Beer", category=category)
    resp = admin_client.delete(DETAIL.format(pk=stock.pk))
    assert resp.status_code == 204
    assert not Stock.objects.filter(pk=stock.pk).exists()


def test_validation_error_returns_400(admin_client, category):
    resp = admin_client.post(
        LIST,
        data=json.dumps({"category": category.pk}),  # missing required name
        content_type="application/json",
    )
    assert resp.status_code == 400
    assert "name" in resp.json()["errors"]


def test_custom_action(admin_client, category):
    s1 = Stock.objects.create(name="Beer", category=category, is_active=True)
    s2 = Stock.objects.create(name="Wine", category=category, is_active=True)
    resp = admin_client.post(
        ACTION,
        data=json.dumps({"ids": [s1.pk, s2.pk]}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    assert resp.json()["result"] == {"updated": 2}
    assert Stock.objects.filter(is_active=False).count() == 2


def test_access_denied_for_user_without_permission(db, category):
    User.objects.create_user("nobody", password="x")
    client = Client()
    client.force_login(User.objects.get(username="nobody"))
    resp = client.get(LIST)
    assert resp.status_code == 403
