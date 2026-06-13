"""Relation-spanning lookups (`a__b`) in list_display and list_filter."""

import pytest
from django.contrib.auth.models import User
from django.test import Client

from tests.testproject.sampleapp.models import Category, House, Stock

LIST = "/theia/api/data/sampleapp.stock/"


@pytest.fixture
def admin_client(db):
    user = User.objects.create_user("root", password="x", is_superuser=True)
    client = Client()
    client.force_login(user)
    return client


@pytest.fixture
def data(db):
    cat = Category.objects.create(name="Drinks")
    h1 = House.objects.create(name="Main")
    h2 = House.objects.create(name="Annex")
    Stock.objects.create(name="Beer", category=cat, house=h1)
    Stock.objects.create(name="Wine", category=cat, house=h2)
    return cat, h1, h2


def test_list_display_resolves_relation_value(admin_client, data):
    rows = admin_client.get(LIST).json()["results"]
    by_name = {r["name"]: r for r in rows}
    assert by_name["Beer"]["house__name"] == "Main"
    assert by_name["Wine"]["house__name"] == "Annex"


def test_filter_by_relation_lookup(admin_client, data):
    resp = admin_client.get(LIST, {"house__name": "Annex"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    assert body["results"][0]["name"] == "Wine"


def test_order_by_relation_lookup(admin_client, data):
    rows = admin_client.get(LIST, {"ordering": "house__name"}).json()["results"]
    # Annex < Main
    assert [r["name"] for r in rows] == ["Wine", "Beer"]
