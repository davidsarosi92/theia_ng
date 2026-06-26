"""The eager subtree endpoint assembles all descendants in one response."""

import pytest
from django.contrib.auth.models import User
from django.test import Client

from tests.testproject.sampleapp.models import Category, House, Space, Stock


@pytest.fixture
def admin_client(db):
    user = User.objects.create_user("root", password="x", is_superuser=True)
    client = Client()
    client.force_login(user)
    return client


@pytest.mark.django_db
def test_tree_full_inlines_all_descendants(admin_client):
    house = House.objects.create(name="Main")
    Space.objects.create(name="Bar", house=house)
    Space.objects.create(name="Terrace", house=house)
    cat = Category.objects.create(name="Drinks")
    Stock.objects.create(name="Beer", category=cat, house=house)

    resp = admin_client.get(f"/theia/api/tree-full/sampleapp.house/{house.pk}/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["truncated"] is False

    root = data["root"]
    assert root["pk"] == house.pk  # House has no tree_parent -> it is the root
    assert root["is_current"] is True
    assert root["perms"]["change"] is True  # superuser

    groups = {g["accessor"]: g for g in root["children"]}
    # Both child relations are inlined eagerly, with the records (not just counts).
    assert {n["label"] for n in groups["spaces"]["nodes"]} == {"Bar", "Terrace"}
    assert {n["label"] for n in groups["stock_set"]["nodes"]} == {"Beer"}


@pytest.mark.django_db
def test_tree_full_roots_at_top_ancestor(admin_client):
    """Opened on a leaf-ish record (a Stock, whose ``tree_parent`` is its House),
    the tree still roots at the House and flags the Stock as current — so the view
    is useful at every level, not just the top."""
    house = House.objects.create(name="Main")
    cat = Category.objects.create(name="Drinks")
    stock = Stock.objects.create(name="Beer", category=cat, house=house)

    resp = admin_client.get(f"/theia/api/tree-full/sampleapp.stock/{stock.pk}/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["root"]["pk"] == house.pk
    assert data["root"]["is_current"] is False
    assert data["current"] == {"key": "sampleapp.stock", "pk": str(stock.pk)}
    stocks = next(g for g in data["root"]["children"] if g["accessor"] == "stock_set")
    assert stocks["nodes"][0]["is_current"] is True


@pytest.mark.django_db
def test_tree_full_caps_at_max_nodes():
    from django.test import RequestFactory

    from theia_ng.introspection.tree import build_full_subtree
    from theia_ng.registry import site

    house = House.objects.create(name="Big")
    for i in range(5):
        Space.objects.create(name=f"S{i}", house=house)

    request = RequestFactory().get("/")
    request.user = User.objects.create_user("u", password="x", is_superuser=True)
    model, admin = site.get_model("sampleapp.house")
    # Cap below the total node count -> truncated, and no more than `max_nodes`.
    data = build_full_subtree(model, admin, house, request, max_nodes=3)
    assert data["truncated"] is True
    spaces = next(g for g in data["root"]["children"] if g["accessor"] == "spaces")
    assert spaces["truncated"] is True
    assert len(spaces["nodes"]) <= 3
