"""Parameterized custom actions (form fields + selection mode)."""

import json

import pytest
from django.contrib.auth.models import User
from django.test import Client

from tests.testproject.sampleapp.models import Category, Stock

SCHEMA = "/theia/api/schema/sampleapp.stock/"
ACTION = "/theia/api/action/sampleapp.stock/{key}/"


@pytest.fixture
def category(db):
    return Category.objects.create(name="Drinks")


@pytest.fixture
def admin_client(db):
    user = User.objects.create_user("root", password="x", is_superuser=True)
    client = Client()
    client.force_login(user)
    return client


def test_schema_exposes_action_fields_and_selection(admin_client):
    actions = {a["key"]: a for a in admin_client.get(SCHEMA).json()["actions"]}

    # plain action: required selection, no fields
    assert actions["deactivate"]["selection"] == "required"
    assert actions["deactivate"]["fields"] == []

    # parameterized action
    add = actions["bulk_add"]
    assert add["label"] == "Bulk add stock"
    assert add["selection"] == "none"
    fields = {f["name"]: f for f in add["fields"]}
    assert fields["name"]["type"] == "string" and fields["name"]["required"]
    assert fields["activate"]["type"] == "boolean"
    # relation field carries a picker descriptor
    rel = fields["category"]["relation"]
    assert rel["target"] == "sampleapp.category"
    assert rel["options_endpoint"] == "data/sampleapp.category/"
    assert rel["registered"] is True


def test_parameterized_action_runs_with_params(admin_client, category):
    resp = admin_client.post(
        ACTION.format(key="bulk_add"),
        data=json.dumps({"ids": [], "params": {
            "name": "Cola", "category": category.pk, "quantity": "5", "activate": True,
        }}),
        content_type="application/json",
    )
    assert resp.status_code == 200, resp.content
    created = Stock.objects.get(name="Cola")
    assert created.category_id == category.pk
    assert str(created.quantity) == "5.00"
    assert created.is_active is True


def test_required_param_missing_returns_errors(admin_client, category):
    resp = admin_client.post(
        ACTION.format(key="bulk_add"),
        data=json.dumps({"ids": [], "params": {"category": category.pk}}),  # no name
        content_type="application/json",
    )
    assert resp.status_code == 400
    assert "name" in resp.json()["errors"]
    assert not Stock.objects.filter(category=category).exists()


def test_plain_action_still_two_arg(admin_client, category):
    s = Stock.objects.create(name="X", category=category, is_active=True)
    resp = admin_client.post(
        ACTION.format(key="deactivate"),
        data=json.dumps({"ids": [s.pk]}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    s.refresh_from_db()
    assert s.is_active is False
