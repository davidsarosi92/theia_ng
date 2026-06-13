"""Lists must not materialize a row's non-displayed (or unbounded) M2M sets."""

import pytest
from django.contrib.auth.models import User
from django.test import Client

from tests.testproject.sampleapp.models import Category, House, Space, Stock

LIST = "/theia/api/data/sampleapp.stock/"


@pytest.fixture
def admin_client(db):
    user = User.objects.create_user("root", password="x", is_superuser=True)
    client = Client()
    client.force_login(user)
    return client


@pytest.fixture
def stocks_with_spaces(db):
    cat = Category.objects.create(name="Drinks")
    house = House.objects.create(name="Main")
    spaces = [Space.objects.create(name=f"S{i}", house=house) for i in range(6)]
    for i in range(4):
        s = Stock.objects.create(name=f"Stock {i}", category=cat, house=house)
        s.spaces.set(spaces)  # every stock has all 6 spaces (m2m)
    return Stock.objects.all()


def test_list_omits_non_displayed_m2m(admin_client, stocks_with_spaces):
    # `spaces` is an M2M that is NOT in StockAdmin.list_display.
    row = admin_client.get(LIST).json()["results"][0]
    assert "spaces" not in row  # not serialized -> not loaded per row
    # displayed columns are present
    assert "name" in row and "category" in row and "house__name" in row


def test_list_query_count_independent_of_m2m(admin_client, stocks_with_spaces, django_assert_max_num_queries):
    admin_client.get(LIST)  # warm up session/auth
    # No per-row M2M prefetch/load: a handful of queries regardless of m2m size.
    with django_assert_max_num_queries(6):
        assert admin_client.get(LIST).status_code == 200
