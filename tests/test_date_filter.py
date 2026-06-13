"""Date/datetime filters: presets + date-only (time optional)."""

import datetime

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.utils import timezone

from tests.testproject.sampleapp.models import Category, Stock

LIST = "/theia/api/data/sampleapp.stock/"


@pytest.fixture
def admin_client(db):
    user = User.objects.create_user("root", password="x", is_superuser=True)
    client = Client()
    client.force_login(user)
    return client


@pytest.fixture
def stocks(db):
    cat = Category.objects.create(name="Drinks")
    now = timezone.now()
    today = Stock.objects.create(name="Today", category=cat, created_at=now)
    old = Stock.objects.create(name="Old", category=cat, created_at=now - datetime.timedelta(days=40))
    year_plus = Stock.objects.create(
        name="Ancient", category=cat, created_at=now - datetime.timedelta(days=400)
    )
    return today, old, year_plus


def _names(resp):
    return {r["name"] for r in resp.json()["results"]}


def test_preset_last_7_days(admin_client, stocks):
    assert _names(admin_client.get(LIST, {"created_at": "last_7_days"})) == {"Today"}


def test_preset_last_30_days(admin_client, stocks):
    # 40-day-old and 400-day-old are excluded; only today's.
    assert _names(admin_client.get(LIST, {"created_at": "last_30_days"})) == {"Today"}


def test_preset_last_year_excludes_older(admin_client, stocks):
    names = _names(admin_client.get(LIST, {"created_at": "last_year"}))
    assert "Today" in names and "Old" in names and "Ancient" not in names


def test_today_preset(admin_client, stocks):
    assert _names(admin_client.get(LIST, {"created_at": "today"})) == {"Today"}


def test_specific_date_without_time(admin_client, stocks):
    """A bare YYYY-MM-DD matches that calendar day (time optional)."""
    today = timezone.localdate().isoformat()
    assert _names(admin_client.get(LIST, {"created_at": today})) == {"Today"}


def test_date_filter_is_a_synthetic_field_in_schema(admin_client, db):
    fields = {f["name"]: f for f in admin_client.get("/theia/api/schema/sampleapp.stock/").json()["fields"]}
    assert fields["created_at"]["type"] == "datetime"
