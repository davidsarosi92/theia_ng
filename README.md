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
- `ModelAdmin`-style config: `list_display` (incl. **computed columns**),
  `list_filter` (field filters + **custom filters**), `search_fields`,
  `ordering`, `readonly_fields`, `exclude`, `raw_id_fields`, `actions`,
  `relation_filters`
- Searchable, paginated relation pickers (FK single, M2M multi) that load options
  on demand — fine for tables with thousands of rows. Related rows carry
  **View / Edit / Delete** actions (permission-aware) and navigate to the record
- M2M selections shown as a **table** above the picker; breadcrumbs + Back so you
  always know where you are
- `get_queryset` and **object-level permissions** hooks for row scoping
- Per-model display control: `display_field` / `display()` for relation labels
- **Menu views** — admin-defined, named subsets of the sidebar (which models, and
  which of their fields), switchable from the top bar; always narrowed by perms
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
    list_display = ["title", "category", "published", "byline"]
    list_filter = ["published", "category"]
    search_fields = ["title"]
    ordering = ["-created"]
    readonly_fields = ["created", "modified"]   # shown, but not editable

    @theia_ng.display(description="Byline")      # computed list_display column
    def byline(self, obj):
        return f"{obj.author} · {obj.created:%Y-%m-%d}"


@theia_ng.register(Category)
class CategoryAdmin(theia_ng.ModelAdmin):
    list_display = ["name"]
    search_fields = ["name"]
```

**4. Migrate** (creates the `theia_ng.access` permission and the `MenuView`
table used by sidebar views — run this after upgrading too):

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
  Override `has_*_permission(self, request, obj=None)` on your `ModelAdmin` to
  plug in a custom scheme. On detail endpoints `obj` is the target instance, so
  you can enforce **object-level** rules:

  ```python
  def has_change_permission(self, request, obj=None):
      if obj is not None:
          return obj.owner_id == request.user.id
      return super().has_change_permission(request)
  ```

## Customizing the form & columns

```python
@theia_ng.register(Article)
class ArticleAdmin(theia_ng.ModelAdmin):
    readonly_fields = ["created_by"]   # shown in the form, but disabled
    exclude = ["internal_notes"]       # dropped from the form entirely
    raw_id_fields = ["author"]         # plain id input instead of a picker
```

- **`readonly_fields`** — rendered in the form, disabled (good for audit fields).
- **`exclude`** — removed from the form (still usable in `list_display`).
- **`raw_id_fields`** — render an FK/M2M as a plain id input rather than the
  searchable picker. Relations whose target model isn't registered fall back to
  this automatically.

## Scoping rows: `get_queryset`

Override the base queryset for both the list and detail (e.g. multi-tenant
scoping, annotations, or `select_related`). Rows it excludes are hidden from
detail/update/delete too, not just the list:

```python
def get_queryset(self, request):
    return super().get_queryset(request).filter(company=request.user.company)
```

## Custom list filters

Field names in `list_filter` build the obvious filters. For anything else, add a
`ListFilter` subclass (the equivalent of `django.contrib.admin.SimpleListFilter`)
— it contributes a labelled dropdown and applies arbitrary queryset logic:

```python
class HasOrdersFilter(theia_ng.ListFilter):
    title = "Has orders"
    parameter_name = "has_orders"

    def lookups(self, request):
        return [("yes", "Has orders"), ("no", "No orders")]

    def queryset(self, request, queryset, value):
        if value == "yes":
            return queryset.filter(orders__isnull=False).distinct()
        if value == "no":
            return queryset.filter(orders__isnull=True)
        return queryset


@theia_ng.register(Customer)
class CustomerAdmin(theia_ng.ModelAdmin):
    list_filter = ["active", HasOrdersFilter]   # mix field + custom filters
```

Choices come from `lookups()` (keep them static — they're cached with the
schema). The filter runs after `get_queryset`, so any annotations are available.

## Menu views

Admins can define named **views** that narrow the left sidebar: which models
appear, and optionally which of each model's fields are shown (in the list and
the form). A view only ever *narrows* within what the user may already see —
permissions are checked first, then the view intersects. Staff switch the active
view from a dropdown in the top bar; "Full" (everything permitted) is always
available.

Views are stored in the built-in `MenuView` model and managed through the admin
itself (no code) — so they're maintainable at runtime. Nothing to configure;
just `migrate` and a "Menu views" entry appears in the sidebar.

## Dependent relation options

Narrow a relation field's options by the **current values of sibling fields** on
the record being edited — e.g. only show `Space`s that belong to the `Stock`'s
selected `house`:

```python
@theia_ng.register(Stock)
class StockAdmin(theia_ng.ModelAdmin):
    relation_filters = {
        "spaces": {"house": "house"},   # {target_lookup: source_field}
    }
```

This loads `Space.objects.filter(house=<the form's current house value>)`. The
picker re-fetches when `house` changes, and shows nothing until it is set. The
filter lookups are **server-defined** (the client only sends the sibling
values), so it can't be used to query arbitrary fields.

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
