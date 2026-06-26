"""@theia_ng.compact_tree surfaces a placeable, read-only hierarchy field."""

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


def test_compact_tree_field_in_schema(admin_client):
    schema = admin_client.get("/theia/api/schema/sampleapp.house/").json()
    field = next(f for f in schema["fields"] if f["name"] == "structure")
    assert field["type"] == "compact_tree"
    assert field["label"] == "Structure"
    assert field["editable"] is False and field["read_only"] is True


@pytest.mark.django_db
def test_compact_tree_field_resolved_on_detail(admin_client):
    house = House.objects.create(name="Main")
    rep = admin_client.get(f"/theia/api/data/sampleapp.house/{house.pk}/").json()
    # The decorator returns ``obj`` -> the field resolves to this House's {key, pk}.
    assert rep["structure"] == {"key": "sampleapp.house", "pk": house.pk}


@pytest.mark.django_db
def test_tree_full_root_self_does_not_climb(admin_client):
    """?root=self roots at the record (descendants only), unlike the default which
    climbs to the topmost ancestor."""
    house = House.objects.create(name="Main")
    cat = Category.objects.create(name="Drinks")
    stock = Stock.objects.create(name="Beer", category=cat, house=house)
    Space.objects.create(name="Bar", house=house)

    # Default (climb): opened on the Stock, the tree roots at its House.
    climbed = admin_client.get(f"/theia/api/tree-full/sampleapp.stock/{stock.pk}/").json()
    assert climbed["root"]["pk"] == house.pk

    # root=self: roots at the Stock itself (a leaf -> no children).
    selfed = admin_client.get(
        f"/theia/api/tree-full/sampleapp.stock/{stock.pk}/?root=self"
    ).json()
    assert selfed["root"]["key"] == "sampleapp.stock"
    assert selfed["root"]["pk"] == stock.pk
    assert selfed["root"]["is_current"] is True
    assert selfed["root"]["children"] == []


@pytest.mark.django_db
def test_tree_full_current_override_highlights_page_record(admin_client):
    """A field rooted at an ancestor still flags the page's actual record: rooting
    at the House but passing ?current=<space> marks the Space, not the House."""
    house = House.objects.create(name="Main")
    space = Space.objects.create(name="Bar", house=house)

    data = admin_client.get(
        f"/theia/api/tree-full/sampleapp.house/{house.pk}/"
        f"?root=self&current=sampleapp.space:{space.pk}"
    ).json()
    assert data["root"]["is_current"] is False  # the House root is not the record
    spaces = next(g for g in data["root"]["children"] if g["accessor"] == "spaces")
    assert spaces["nodes"][0]["is_current"] is True  # the Space is
