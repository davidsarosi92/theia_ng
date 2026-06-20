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


def test_detail_actions_in_schema(admin_client):
    actions = {a["key"]: a for a in admin_client.get(SCHEMA).json()["actions"]}
    # object actions are flagged `detail` (the SPA shows them on the detail page)
    assert actions["archive"]["detail"] is True
    assert actions["archive"]["dangerous"] is True
    assert actions["rename_to"]["detail"] is True
    assert [f["name"] for f in actions["rename_to"]["fields"]] == ["name"]
    # list/bulk actions are not detail actions
    assert actions["deactivate"]["detail"] is False
    assert actions["delete_selected"]["detail"] is False


def test_detail_action_runs_on_single_record(admin_client, category):
    a = Stock.objects.create(name="A", category=category, is_active=True)
    b = Stock.objects.create(name="B", category=category, is_active=True)
    # run the detail action over just this record (ids=[a.pk]), like the detail page
    resp = admin_client.post(
        ACTION.format(key="rename_to"),
        data=json.dumps({"ids": [a.pk], "params": {"name": "Renamed"}}),
        content_type="application/json",
    )
    assert resp.status_code == 200, resp.content
    a.refresh_from_db(); b.refresh_from_db()
    assert a.name == "Renamed" and b.name == "B"


def test_schema_exposes_delete_selected_and_selectable(admin_client):
    schema = admin_client.get(SCHEMA).json()
    assert schema["list"]["selectable"] is True
    actions = {a["key"]: a for a in schema["actions"]}
    delete = actions["delete_selected"]
    assert delete["selection"] == "required"
    assert delete["dangerous"] is True
    assert delete["requires"] == "delete"
    # custom actions advertise the permission they need
    assert actions["deactivate"]["requires"] == "change"


def test_delete_selected_by_ids(admin_client, category):
    a = Stock.objects.create(name="A", category=category)
    b = Stock.objects.create(name="B", category=category)
    c = Stock.objects.create(name="C", category=category)
    resp = admin_client.post(
        ACTION.format(key="delete_selected"),
        data=json.dumps({"ids": [a.pk, b.pk]}),
        content_type="application/json",
    )
    assert resp.status_code == 200, resp.content
    assert resp.json()["result"]["deleted"] == 2
    assert list(Stock.objects.values_list("pk", flat=True)) == [c.pk]


def test_delete_selected_all_matching_filter(admin_client, category):
    other = Category.objects.create(name="Other")
    Stock.objects.create(name="A", category=category)
    Stock.objects.create(name="B", category=category)
    keep = Stock.objects.create(name="C", category=other)
    # "select all matching" the category filter -> deletes only that category
    resp = admin_client.post(
        ACTION.format(key="delete_selected"),
        data=json.dumps({"all": True, "filters": {"category": category.pk}}),
        content_type="application/json",
    )
    assert resp.status_code == 200, resp.content
    assert resp.json()["result"]["deleted"] == 2
    assert list(Stock.objects.values_list("pk", flat=True)) == [keep.pk]


def test_delete_selected_requires_delete_permission(category):
    # a user without delete permission is forbidden
    staff = User.objects.create_user("staff", password="x")
    staff.is_staff = True
    staff.save()
    Stock.objects.create(name="A", category=category)
    client = Client()
    client.force_login(staff)
    resp = client.post(
        ACTION.format(key="delete_selected"),
        data=json.dumps({"ids": [Stock.objects.first().pk]}),
        content_type="application/json",
    )
    assert resp.status_code in (403, 302)
    assert Stock.objects.count() == 1  # nothing deleted
