"""Self-service change-password endpoint."""

import json

import pytest
from django.contrib.auth.models import User
from django.test import Client

URL = "/theia/api/change-password/"


@pytest.fixture
def client(db):
    user = User.objects.create_user("root", password="old-pass-123", is_superuser=True)
    c = Client()
    c.force_login(user)
    return c, user


def _post(client, body):
    return client.post(URL, data=json.dumps(body), content_type="application/json")


def test_change_password_success(client):
    c, user = client
    resp = _post(c, {"current_password": "old-pass-123", "new_password": "brand-new-456"})
    assert resp.status_code == 200
    user.refresh_from_db()
    assert user.check_password("brand-new-456")
    # session is kept alive (update_session_auth_hash) -> still authenticated.
    assert c.get("/theia/api/me/").json()["authenticated"] is True


def test_wrong_current_password_rejected(client):
    c, user = client
    resp = _post(c, {"current_password": "nope", "new_password": "brand-new-456"})
    assert resp.status_code == 400
    user.refresh_from_db()
    assert user.check_password("old-pass-123")  # unchanged


def test_weak_new_password_rejected(client):
    c, user = client
    resp = _post(c, {"current_password": "old-pass-123", "new_password": "1"})
    assert resp.status_code == 400  # fails the configured password validators
    user.refresh_from_db()
    assert user.check_password("old-pass-123")


@pytest.mark.django_db
def test_anonymous_forbidden():
    assert _post(Client(), {"current_password": "x", "new_password": "y"}).status_code == 403
