"""Session login/logout endpoints."""

import json

from django.contrib.auth.models import User


def test_me_anonymous(client, db):
    r = client.get("/theia/api/me/")
    assert r.status_code == 200
    body = r.json()
    assert body["authenticated"] is False
    assert body["can_access"] is False
    assert body["username"] is None


def test_login_then_me_then_logout(client, db):
    User.objects.create_user("root", password="pw", is_superuser=True)

    r = client.post(
        "/theia/api/login/",
        data=json.dumps({"username": "root", "password": "pw"}),
        content_type="application/json",
    )
    assert r.status_code == 200
    assert r.json() == {"authenticated": True, "username": "root", "can_access": True}

    # session now carries the user
    assert client.get("/theia/api/me/").json()["authenticated"] is True

    r = client.post("/theia/api/logout/")
    assert r.status_code == 200
    assert client.get("/theia/api/me/").json()["authenticated"] is False


def test_login_rejects_bad_credentials(client, db):
    User.objects.create_user("root", password="pw")
    r = client.post(
        "/theia/api/login/",
        data=json.dumps({"username": "root", "password": "WRONG"}),
        content_type="application/json",
    )
    assert r.status_code == 400
    assert "detail" in r.json()
