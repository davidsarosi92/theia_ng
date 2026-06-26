"""URL patterns mounted under a single configurable prefix.

In the host project::

    urlpatterns = [
        path("theia/", include("theia_ng.urls")),
    ]

Within the prefix: ``/`` -> SPA, ``/api/`` -> schema + data + actions.
"""

from __future__ import annotations

from django.urls import include, path, re_path

from theia_ng.api import (
    auth_views,
    favorites_views,
    log_views,
    schema_views,
    settings_views,
    siteconfig_views,
)
from theia_ng.api.crud_views import (
    ActionView,
    DataDetailView,
    DataListView,
    RelationOptionsView,
    TreeChildrenView,
    TreeFullView,
    TreeView,
)
from theia_ng.views import spa

app_name = "theia_ng"

# A model key looks like "app_label.model_name".
_KEY = r"(?P<model_key>[a-zA-Z0-9_]+\.[a-zA-Z0-9_]+)"

api_patterns = [
    path("me/", auth_views.me, name="me"),
    path("login/", auth_views.login_view, name="login"),
    path("logout/", auth_views.logout_view, name="logout"),
    path("favorites/", favorites_views.favorites, name="favorites"),
    path("settings/", settings_views.settings, name="settings"),
    path("site-config/", siteconfig_views.site_config, name="site-config"),
    path("site-config/clear-cache/", siteconfig_views.clear_cache, name="clear-cache"),
    path("logs/", log_views.logs, name="logs"),
    path("schema/", schema_views.schema_registry, name="schema-registry"),
    re_path(rf"^schema/{_KEY}/$", schema_views.schema_model, name="schema-model"),
    re_path(
        rf"^relation-options/{_KEY}/(?P<field>[a-zA-Z0-9_]+)/$",
        RelationOptionsView.as_view(),
        name="relation-options",
    ),
    re_path(rf"^tree/{_KEY}/(?P<pk>[^/]+)/$", TreeView.as_view(), name="tree"),
    re_path(rf"^tree-full/{_KEY}/(?P<pk>[^/]+)/$", TreeFullView.as_view(), name="tree-full"),
    re_path(
        rf"^tree-children/{_KEY}/(?P<pk>[^/]+)/(?P<accessor>[a-zA-Z0-9_]+)/$",
        TreeChildrenView.as_view(),
        name="tree-children",
    ),
    re_path(rf"^data/{_KEY}/$", DataListView.as_view(), name="data-list"),
    re_path(rf"^data/{_KEY}/(?P<pk>[^/]+)/$", DataDetailView.as_view(), name="data-detail"),
    re_path(rf"^action/{_KEY}/(?P<action_key>[a-zA-Z0-9_]+)/$", ActionView.as_view(), name="action"),
]

urlpatterns = [
    path("api/", include((api_patterns, "api"))),
    # SPA catch-all: serves bundle assets, else index.html. Must come last.
    re_path(r"^(?P<asset_path>.*)$", spa, name="spa"),
]
