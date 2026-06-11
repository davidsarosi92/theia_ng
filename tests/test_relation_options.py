"""Dependent relation options: ModelAdmin.relation_filters."""

import pytest
from django.contrib.auth.models import User
from django.test import Client

from tests.testproject.sampleapp.models import House, Space

ENDPOINT = "/theia/api/relation-options/sampleapp.stock/spaces/"


@pytest.fixture
def admin_client(db):
    user = User.objects.create_user("root", password="x", is_superuser=True)
    client = Client()
    client.force_login(user)
    return client


@pytest.fixture
def houses(db):
    h1 = House.objects.create(name="H1")
    h2 = House.objects.create(name="H2")
    Space.objects.create(name="S1a", house=h1)
    Space.objects.create(name="S1b", house=h1)
    Space.objects.create(name="S2", house=h2)
    return h1, h2


def test_options_filtered_by_sibling_value(admin_client, houses):
    h1, _ = houses
    resp = admin_client.get(ENDPOINT, {"house": h1.pk})
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 2
    assert {r["name"] for r in body["results"]} == {"S1a", "S1b"}
    # Every option carries a __str__ label so pickers can show the object,
    # not just one column (defaults to the model's __str__).
    assert all(r["__str__"] == str(r["name"]) for r in body["results"])


def test_other_house_returns_only_its_spaces(admin_client, houses):
    _, h2 = houses
    resp = admin_client.get(ENDPOINT, {"house": h2.pk})
    assert resp.json()["count"] == 1
    assert resp.json()["results"][0]["name"] == "S2"


def test_missing_dependency_returns_no_options(admin_client, houses):
    # No `house` supplied -> the dependency is unmet -> empty.
    resp = admin_client.get(ENDPOINT)
    assert resp.status_code == 200
    assert resp.json()["count"] == 0


def test_search_within_filtered_options(admin_client, houses):
    h1, _ = houses
    resp = admin_client.get(ENDPOINT, {"house": h1.pk, "search": "S1a"})
    assert resp.json()["count"] == 1
    assert resp.json()["results"][0]["name"] == "S1a"


def test_unknown_relation_filter_is_404(admin_client, houses):
    resp = admin_client.get("/theia/api/relation-options/sampleapp.stock/category/")
    assert resp.status_code == 404
