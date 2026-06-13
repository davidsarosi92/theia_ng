"""list_select_related / list_prefetch_related avoid N+1 in the list query."""

import pytest
from django.contrib.auth.models import User
from django.test import Client

from tests.testproject.sampleapp.models import House, Space

HOUSE_LIST = "/theia/api/data/sampleapp.house/"


@pytest.fixture
def admin_client(db):
    user = User.objects.create_user("root", password="x", is_superuser=True)
    client = Client()
    client.force_login(user)
    return client


@pytest.fixture
def houses(db):
    for i in range(5):
        h = House.objects.create(name=f"House {i}")
        Space.objects.create(name=f"Bar {i}", house=h)
        Space.objects.create(name=f"Terrace {i}", house=h)
    return House.objects.all()


def test_prefetch_avoids_n_plus_one(admin_client, houses, django_assert_max_num_queries):
    """``space_names`` walks the reverse ``spaces`` relation for every row;
    ``list_prefetch_related = ["spaces"]`` keeps the query count flat as houses
    grow (one prefetch query, not one per house). Without it, 5 houses would add
    ~5 extra queries; the bound below is well under that."""
    # Warm up auth/session queries with a first call, then measure a clean one.
    admin_client.get(HOUSE_LIST)
    with django_assert_max_num_queries(6):
        resp = admin_client.get(HOUSE_LIST)
    assert resp.status_code == 200
    rows = {r["name"]: r for r in resp.json()["results"]}
    # the computed column is populated from the prefetched spaces
    assert rows["House 0"]["space_names"] in ("Bar 0, Terrace 0", "Terrace 0, Bar 0")


def test_list_still_correct_with_select_related(admin_client, houses):
    # Sanity: rows render with the prefetched column for all houses.
    rows = admin_client.get(HOUSE_LIST).json()["results"]
    assert len(rows) == 5
    assert all(r["space_names"] for r in rows)
