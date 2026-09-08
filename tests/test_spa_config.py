"""The SPA config script must actually execute in the browser.

Regression guard: ``index.html`` carries a comment that mentions ``</head>``
literally, and injecting before the *first* match buried the config inside that
comment. Everything kept working — the fallbacks and the site-config API masked
it — except values with no other source.
"""

import re

import pytest
from django.contrib.auth.models import User
from django.test import Client


@pytest.fixture
def client_logged_in(db):
    c = Client()
    c.force_login(User.objects.create_user("root", password="x", is_superuser=True))
    return c


def _strip_comments(html: str) -> str:
    return re.sub(r"<!--.*?-->", "", html, flags=re.S)


def test_config_script_is_outside_any_comment(client_logged_in):
    html = client_logged_in.get("/theia/").content.decode()
    assert "__THEIA_NG_CONFIG__" in html, "config not injected at all"
    # The assertion that matters: it survives comment stripping, i.e. a browser
    # would actually execute it.
    assert "__THEIA_NG_CONFIG__" in _strip_comments(html)


def test_config_script_is_inside_head(client_logged_in):
    html = _strip_comments(client_logged_in.get("/theia/").content.decode())
    head = html[: html.rfind("</head>")]
    assert "__THEIA_NG_CONFIG__" in head


def test_config_carries_the_keys_with_no_api_fallback(client_logged_in):
    """`assistEnabled` (and the locale defaults) exist only here — if the script
    does not run, they silently take the SPA's fallback values."""
    html = _strip_comments(client_logged_in.get("/theia/").content.decode())
    for key in ("assistEnabled", "defaultLanguage", "defaultTimezone", "basePrefix"):
        assert f'"{key}"' in html, key
