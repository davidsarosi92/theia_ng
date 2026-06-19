"""Audit logging of writes + the logs read endpoint."""

import json

import pytest
from django.contrib.auth.models import Permission, User
from django.test import Client

from theia_ng.models import LogEntry
from tests.testproject.sampleapp.models import Category, Stock

STOCK = "/theia/api/data/sampleapp.stock/"
LOGS = "/theia/api/logs/"


@pytest.fixture
def category(db):
    return Category.objects.create(name="Drinks")


@pytest.fixture
def admin_client(db):
    user = User.objects.create_user("root", password="x", is_superuser=True)
    client = Client()
    client.force_login(user)
    return client


def _create_stock(client, category, **extra):
    payload = {"name": "Beer", "category": category.pk, "quantity": "10.00", **extra}
    return client.post(STOCK, data=json.dumps(payload), content_type="application/json")


def test_create_is_logged_with_changes(admin_client, category):
    _create_stock(admin_client, category)
    entry = LogEntry.objects.get()
    assert entry.action == "create"
    assert entry.model_key == "sampleapp.stock"
    assert entry.username == "root"
    assert entry.object_repr == "Beer"
    assert entry.changes["name"] == [None, "Beer"]


def test_update_logs_field_diff(admin_client, category):
    pk = _create_stock(admin_client, category).json()["pk"]
    admin_client.patch(
        f"{STOCK}{pk}/", data=json.dumps({"quantity": "8.00"}), content_type="application/json"
    )
    entry = LogEntry.objects.filter(action="update").get()
    assert entry.changes["quantity"] == ["10.00", "8.00"]
    assert "name" not in entry.changes  # unchanged fields are not recorded


def test_delete_is_logged(admin_client, category):
    pk = _create_stock(admin_client, category).json()["pk"]
    admin_client.delete(f"{STOCK}{pk}/")
    entry = LogEntry.objects.filter(action="delete").get()
    assert entry.object_pk == str(pk)
    assert entry.object_repr == "Beer"


def test_action_is_logged(admin_client, category):
    s = Stock.objects.create(name="X", category=category)
    admin_client.post(
        "/theia/api/action/sampleapp.stock/deactivate/",
        data=json.dumps({"ids": [s.pk]}),
        content_type="application/json",
    )
    entry = LogEntry.objects.filter(action="action").get()
    assert entry.changes["action"] == "deactivate"
    assert entry.changes["ids"] == [str(s.pk)]
    # `count` is recorded too, so the UI can show it for select-all actions.
    assert entry.changes["count"] == 1


def test_delete_selected_is_logged_with_count(admin_client, category):
    a = Stock.objects.create(name="A", category=category)
    b = Stock.objects.create(name="B", category=category)
    admin_client.post(
        "/theia/api/action/sampleapp.stock/delete_selected/",
        data=json.dumps({"ids": [a.pk, b.pk]}),
        content_type="application/json",
    )
    entry = LogEntry.objects.filter(action="action").get()
    assert entry.changes["action"] == "delete_selected"
    assert entry.changes["count"] == 2
    assert entry.changes["all"] is False
    assert entry.object_repr == "delete_selected (2 objects)"


def test_delete_selected_all_matching_is_logged_with_count(admin_client, category):
    other = Category.objects.create(name="Other")
    Stock.objects.create(name="A", category=category)
    Stock.objects.create(name="B", category=category)
    Stock.objects.create(name="C", category=other)
    admin_client.post(
        "/theia/api/action/sampleapp.stock/delete_selected/",
        data=json.dumps({"all": True, "filters": {"category": category.pk}}),
        content_type="application/json",
    )
    entry = LogEntry.objects.filter(action="action").get()
    assert entry.changes["all"] is True
    # count is authoritative even though no ids were sent.
    assert entry.changes["count"] == 2


def test_logs_endpoint_scopes_to_own_by_default(db, category):
    """A non-superuser sees only their own entries; a superuser sees all."""
    alice = User.objects.create_user("alice", password="x")
    alice.user_permissions.add(
        Permission.objects.get(codename="access", content_type__app_label="theia_ng")
    )
    for codename in ("add_stock", "view_stock"):
        alice.user_permissions.add(
            Permission.objects.get(codename=codename, content_type__app_label="sampleapp")
        )
    ca = Client()
    ca.force_login(alice)
    _create_stock(ca, category)

    # superuser also writes one
    root = User.objects.create_user("root", password="x", is_superuser=True)
    croot = Client()
    croot.force_login(root)
    _create_stock(croot, category)

    # alice sees only her own
    body = ca.get(LOGS).json()
    assert body["is_superuser"] is False
    assert {e["username"] for e in body["results"]} == {"alice"}

    # root sees both, and can filter by user
    all_body = croot.get(LOGS).json()
    assert all_body["is_superuser"] is True
    assert {e["username"] for e in all_body["results"]} == {"alice", "root"}
    filtered = croot.get(LOGS, {"user": "alice"}).json()
    assert {e["username"] for e in filtered["results"]} == {"alice"}


def test_logs_filter_by_action(admin_client, category):
    pk = _create_stock(admin_client, category).json()["pk"]
    admin_client.delete(f"{STOCK}{pk}/")
    body = admin_client.get(LOGS, {"action": "delete"}).json()
    assert body["count"] == 1
    assert body["results"][0]["action"] == "delete"


def test_logs_requires_access(db):
    assert Client().get(LOGS).status_code == 403
