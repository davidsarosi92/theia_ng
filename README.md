# Theia NG

> A dynamic Angular admin for Django, generated from your models — no build step.

**Theia NG** brings a `django.contrib.admin`-style experience to a modern
Angular SPA. You register your models the way you already know, and Theia NG
serves a full CRUD admin introspected from your ORM **at runtime**. No code
generation on your side, no Node toolchain to install — the compiled Angular app
ships inside the wheel.

> ℹ️ Named after Theia, the Titaness of sight. Referred to as **Theia NG** to
> avoid confusion with the Eclipse Theia IDE.

---

## Why

- **ORM is the source of truth.** Theia NG mirrors your Django *models*, not your
  API. Like the built-in admin, it ships its own auto-CRUD layer, so it works
  with **any** Django project — Django REST Framework is *not* required.
- **No dependency on `django.contrib.admin`.** It builds on
  `django.contrib.auth` for permissions and uses the admin only as a design
  reference. Its `ModelAdmin`-style registry is its own.
- **Dynamic, not generated.** Models are introspected at runtime and served as a
  small intermediate representation the SPA consumes. Model changes show up
  immediately; there is no client-side build.
- **One prefix, runtime-configured bundle.** The SPA and its API mount under a
  single configurable prefix; the prebuilt bundle is prefix-independent.

## Features

- Auto-CRUD: list with **search, filtering, sorting, pagination**; create /
  update / delete; custom server-side actions
- `ModelAdmin`-style config: `list_display`, `list_filter`, `search_fields`,
  `ordering`, `readonly_fields`, `actions`
- Searchable, paginated relation pickers (FK single, M2M multi) that load options
  on demand — fine for tables with thousands of rows
- Session login built into the SPA, gated by the `theia_ng.access` permission
- Sidebar grouped by Django app; sticky top bar with sign-out
- Optional **DRF delegation** (use your serializers) and **OpenAPI enrichment** —
  both lazy, so the core never imports DRF

## Requirements

- Python 3.11+
- Django 4.2 LTS or 5.2 LTS
- Django REST Framework 3.14+ *(optional, only for DRF delegation)*

## Installation

```bash
pip install theia_ng
```

## Quickstart

**1. Add the app** to `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    # …
    "django.contrib.auth",
    "theia_ng",
]
```

**2. Mount it** under any prefix in your root `urls.py`:

```python
from django.urls import include, path

urlpatterns = [
    path("theia/", include("theia_ng.urls")),
]
```

**3. Register models** in an app's `theia.py` (autodiscovered, like `admin.py`):

```python
import theia_ng
from myapp.models import Article, Category


@theia_ng.register(Article)
class ArticleAdmin(theia_ng.ModelAdmin):
    list_display = ["title", "category", "published", "created"]
    list_filter = ["published", "category"]
    search_fields = ["title"]
    ordering = ["-created"]
    readonly_fields = ["created", "modified"]


@theia_ng.register(Category)
class CategoryAdmin(theia_ng.ModelAdmin):
    list_display = ["name"]
    search_fields = ["name"]
```

**4. Migrate** (creates the `theia_ng.access` permission):

```bash
python manage.py migrate
```

**5. Grant access** — superusers always pass; otherwise give a user the
`theia_ng.access` permission (plus the usual per-model `view/add/change/delete`
permissions). Open `…/theia/` and sign in.

## Configuration

All optional, via a `THEIA_NG` dict in settings:

```python
THEIA_NG = {
    "SITE_TITLE": "My Admin",   # shown in the top bar
    "MOUNT_PREFIX": "/theia/",  # usually auto-detected from the request
    "SCHEMA_TTL": 300,          # IR cache TTL in seconds (0 disables caching)
    "CACHE_VERSION": "1",       # bump to invalidate the IR cache on deploy
}
```

The introspected schema is cached (structure only; per-user permissions are
always computed fresh). Configure a shared cache backend (e.g. Redis) in
production so all workers agree.

## Permissions & auth

- The SPA uses Django **session auth** (same origin). It sends the CSRF token as
  `X-CSRFToken`, so keep the default `csrftoken` cookie readable
  (`CSRF_COOKIE_HTTPONLY = False`, the Django default).
- Entry is gated by the `theia_ng.access` permission — **not** `is_staff`, so it
  never collides with the Django admin.
- Per-model access uses the standard `view/add/change/delete` permissions.
  Override `has_*_permission(self, request)` on your `ModelAdmin` to plug in a
  custom scheme.

## Optional: DRF delegation

If a model already has a DRF serializer, let Theia NG defer to it for
(de)serialization and validation:

```python
@theia_ng.register(Article)
class ArticleAdmin(theia_ng.ModelAdmin):
    serializer_class = ArticleSerializer
```

The serializer also enriches the schema (required / read-only / help text). DRF
is imported lazily — if you don't use this, you don't need DRF installed.

## License

MIT — see [LICENSE](LICENSE).
