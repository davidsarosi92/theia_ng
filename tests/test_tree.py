"""End-to-end tests for the lazy hierarchy tree endpoints."""

import pytest
from django.contrib.auth.models import Permission, User
from django.test import Client

from tests.testproject.sampleapp.models import Category, House, Space, Stock

TREE = "/theia/api/tree/{key}/{pk}/"
CHILDREN = "/theia/api/tree-children/{key}/{pk}/{accessor}/"


@pytest.fixture
def admin_client(db):
    user = User.objects.create_user("root", password="x", is_superuser=True)
    client = Client()
    client.force_login(user)
    return client


@pytest.fixture
def hierarchy(db):
    house = House.objects.create(name="Main House")
    bar = Space.objects.create(name="Bar", house=house)
    Space.objects.create(name="Terrace", house=house)
    category = Category.objects.create(name="Drinks")
    Stock.objects.create(name="Beer", category=category, house=house)
    return house, bar


def _group(node, key):
    return next(g for g in node["child_groups"] if g["key"] == key)


def test_tree_root_lists_child_groups_with_counts(admin_client, hierarchy):
    house, _ = hierarchy
    resp = admin_client.get(TREE.format(key="sampleapp.house", pk=house.pk))
    assert resp.status_code == 200, resp.content
    body = resp.json()
    root = body["root"]
    assert root["model_label"] == "house"
    assert root["is_current"] is True
    # Counts only — no records inlined.
    assert _group(root, "sampleapp.space")["count"] == 2
    assert _group(root, "sampleapp.stock")["count"] == 1
    assert body["path"] == [{"key": "sampleapp.house", "pk": house.pk}]


def test_tree_walks_up_from_leaf_with_path(admin_client, hierarchy):
    """Opening from a Space roots at the House and returns the lineage path."""
    house, bar = hierarchy
    body = admin_client.get(TREE.format(key="sampleapp.space", pk=bar.pk)).json()
    assert body["root"]["model_label"] == "house"
    assert body["root"]["pk"] == house.pk
    assert body["current"] == {"key": "sampleapp.space", "pk": bar.pk}
    assert body["path"] == [
        {"key": "sampleapp.house", "pk": house.pk},
        {"key": "sampleapp.space", "pk": bar.pk},
    ]


def test_children_endpoint_paginates_and_searches(admin_client, hierarchy):
    house, _ = hierarchy
    resp = admin_client.get(CHILDREN.format(key="sampleapp.house", pk=house.pk, accessor="spaces"))
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["count"] == 2
    labels = {r["label"] for r in body["results"]}
    assert labels == {"Bar", "Terrace"}
    # Each child is a node carrying its own (empty) child groups.
    assert all("child_groups" in r for r in body["results"])

    # Search narrows the set server-side (Space.search_fields = ["name"]).
    body = admin_client.get(
        CHILDREN.format(key="sampleapp.house", pk=house.pk, accessor="spaces"), {"search": "Terr"}
    ).json()
    assert body["count"] == 1
    assert body["results"][0]["label"] == "Terrace"


def test_children_focus_jumps_to_page(admin_client, db):
    """`focus` returns the page holding that child pk."""
    house = House.objects.create(name="Big")
    spaces = [Space.objects.create(name=f"S{i}", house=house) for i in range(120)]
    # list_per_page defaults to 50 -> the 60th space is on page 2.
    target = spaces[59]
    body = admin_client.get(
        CHILDREN.format(key="sampleapp.house", pk=house.pk, accessor="spaces"),
        {"focus": target.pk},
    ).json()
    assert body["page"] == 2
    assert any(r["pk"] == target.pk for r in body["results"])


def test_children_rejects_unknown_accessor(admin_client, hierarchy):
    house, _ = hierarchy
    resp = admin_client.get(CHILDREN.format(key="sampleapp.house", pk=house.pk, accessor="bogus_set"))
    assert resp.status_code == 404


def test_children_excludes_unviewable_model(db, hierarchy):
    """A child group the user can't view is omitted from the node, and its
    children endpoint is forbidden."""
    house, _ = hierarchy
    user = User.objects.create_user("limited", password="x")
    user.user_permissions.add(
        Permission.objects.get(codename="access", content_type__app_label="theia_ng")
    )
    for model in ("house", "space"):
        user.user_permissions.add(
            Permission.objects.get(codename=f"view_{model}", content_type__app_label="sampleapp")
        )
    client = Client()
    client.force_login(user)
    body = client.get(TREE.format(key="sampleapp.house", pk=house.pk)).json()
    group_keys = {g["key"] for g in body["root"]["child_groups"]}
    assert "sampleapp.space" in group_keys
    assert "sampleapp.stock" not in group_keys  # no view perm on Stock
    # And the stock children endpoint is forbidden.
    resp = client.get(CHILDREN.format(key="sampleapp.house", pk=house.pk, accessor="stock_set"))
    assert resp.status_code == 403


def test_schema_advertises_tree(admin_client, db):
    body = admin_client.get("/theia/api/schema/sampleapp.house/").json()
    assert body["tree"] is True
    body = admin_client.get("/theia/api/schema/sampleapp.category/").json()
    assert body["tree"] is False
