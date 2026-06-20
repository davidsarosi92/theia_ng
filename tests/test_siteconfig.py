"""Admin site-config overrides: API + effective-config resolution + cache flush."""

import json

import pytest
from django.contrib.auth.models import Permission, User
from django.test import Client, override_settings

URL = "/theia/api/site-config/"
CLEAR = "/theia/api/site-config/clear-cache/"


@pytest.fixture
def admin_client(db):
    user = User.objects.create_user("root", password="x", is_superuser=True)
    c = Client()
    c.force_login(user)
    return c


@pytest.fixture
def plain_client(db):
    """An access-having but non-superuser user."""
    u = User.objects.create_user("joe", password="x")
    u.user_permissions.add(
        Permission.objects.get(codename="access", content_type__app_label="theia_ng")
    )
    c = Client()
    c.force_login(u)
    return c


def _patch(c, body):
    return c.patch(URL, data=json.dumps(body), content_type="application/json")


@override_settings(THEIA_NG={"SITE_TITLE": "Deploy Title", "SCHEMA_TTL": 300, "CACHE_VERSION": "1"})
def test_get_returns_defaults_and_empty_overrides(admin_client):
    body = admin_client.get(URL).json()
    assert body["defaults"]["site_title"] == "Deploy Title"
    assert body["defaults"]["schema_ttl"] == 300
    assert body["overrides"]["site_title"] == ""
    assert body["overrides"]["schema_ttl"] is None
    assert body["effective"]["site_title"] == "Deploy Title"


def test_non_superuser_forbidden(plain_client):
    assert plain_client.get(URL).status_code == 403
    assert plain_client.patch(URL, data="{}", content_type="application/json").status_code == 403
    assert plain_client.post(CLEAR).status_code == 403


def test_anonymous_forbidden(db):
    assert Client().get(URL).status_code == 403


@override_settings(THEIA_NG={"SITE_TITLE": "Deploy Title", "SCHEMA_TTL": 300})
def test_patch_overrides_then_conf_resolves(admin_client):
    resp = _patch(admin_client, {"site_title": "Custom", "schema_ttl": 60})
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["overrides"]["site_title"] == "Custom"
    assert body["effective"]["site_title"] == "Custom"
    assert body["effective"]["schema_ttl"] == 60

    # The effective-config resolver (used for cache keys / topbar) sees the override.
    from theia_ng.siteconfig import conf

    assert conf()["SITE_TITLE"] == "Custom"
    assert conf()["SCHEMA_TTL"] == 60


@override_settings(THEIA_NG={"SITE_TITLE": "Deploy Title"})
def test_reset_clears_overrides(admin_client):
    _patch(admin_client, {"site_title": "Custom"})
    body = admin_client.delete(URL).json()
    assert body["overrides"]["site_title"] == ""
    assert body["effective"]["site_title"] == "Deploy Title"
    from theia_ng.siteconfig import conf

    assert conf().get("SITE_TITLE") == "Deploy Title"


def test_schema_ttl_validation(admin_client):
    assert _patch(admin_client, {"schema_ttl": -5}).status_code == 400
    assert _patch(admin_client, {"schema_ttl": "abc"}).status_code == 400
    # empty clears the override (back to default)
    assert _patch(admin_client, {"schema_ttl": ""}).status_code == 200


def test_logo_url_resolution():
    """Absolute URLs pass through; bare paths resolve via Django static()."""
    from theia_ng.siteconfig import logo_url

    with override_settings(THEIA_NG={"LOGO_URL": "https://cdn.example/logo.png"}):
        assert logo_url() == "https://cdn.example/logo.png"
    with override_settings(THEIA_NG={"LOGO_URL": "/media/logo.png"}):
        assert logo_url() == "/media/logo.png"
    with override_settings(THEIA_NG={"LOGO_URL": "admin/imgs/logo.png"}, STATIC_URL="/static/"):
        # static() prefixes STATIC_URL.
        assert logo_url() == "/static/admin/imgs/logo.png"
    with override_settings(THEIA_NG={}):
        assert logo_url() == ""


@override_settings(THEIA_NG={"LOGO_URL": "admin/imgs/logo.png"}, STATIC_URL="/static/")
def test_site_config_effective_logo_is_resolved(admin_client):
    body = admin_client.get(URL).json()
    assert body["effective"]["logo_url"] == "/static/admin/imgs/logo.png"


def test_clear_cache_bumps_buster_and_changes_key(admin_client):
    from theia_ng import cache as ircache

    before_key = ircache._key("model:x")
    before = admin_client.get(URL).json()["cache_buster"]
    resp = admin_client.post(CLEAR)
    assert resp.status_code == 200
    assert resp.json()["cache_buster"] == before + 1
    # the IR cache key now differs -> old cached entries are bypassed
    assert ircache._key("model:x") != before_key
