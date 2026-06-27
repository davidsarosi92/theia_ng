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
- `ModelAdmin`-style config: `list_display` (incl. **computed columns** and
  **relation lookups** like `house__company__name`), `list_filter` (field
  filters + **custom filters** + **date presets**), `search_fields`, `ordering`,
  `readonly_fields`, `exclude`, `raw_id_fields`, `actions`, `relation_filters`,
  **`fieldsets`**, **`list_editable`**, **`inlines`**
- **Inlines** — edit related child rows on the parent's form (`theia_ng.Inline`,
  tabular or stacked); created / updated / deleted in one transaction
- **Fieldsets** — group form fields into sections (optional heading, description,
  collapsible) — and **`list_editable`** — edit cells inline in the list
- **Relation-spanning lookups** (`a__b__c`) in `list_display` / `list_filter`:
  labelled, sortable, and filterable with no extra code
- **Date filters** with relative presets (today, last 2 / 7 / 30 days, last year)
  or a specific day (time optional); **locale- and timezone-aware** date rendering
  in the user's chosen language and timezone
- **Parameterized actions** — actions that pop a form (text, choices, relation
  pickers, …) and run server-side; `selection="none"` for global actions like a
  broadcast
- **Audit log** — every write (create / update / delete / action) is recorded
  with a field-level diff; users see their own trail, superusers see everyone's
- Searchable, paginated relation pickers (FK single, M2M multi) that load options
  on demand — fine for tables with thousands of rows. Related rows carry
  **View / Edit / Delete** actions (permission-aware) and navigate to the record
- M2M selections shown as a **table** above the picker; breadcrumbs + Back so you
  always know where you are
- **raw_id fields** get a modal table picker (searchable, paginated, loads only
  on open) that pre-selects current assignments and works purely by pk; a raw FK
  with a value also offers **View / Edit** buttons to jump to the related record
- **Toast notifications** for every operation (green success / red error,
  top-right, auto-dismiss); **Save and continue editing**
- **Skeleton loaders** on the list and home cards while data loads (no empty
  flash) — the list shows full-row skeleton bars on every page load (no spinner),
  so stale rows never linger during pagination
- `get_queryset`, **`list_select_related` / `list_prefetch_related`**, and
  **object-level permissions** hooks for row scoping and N+1 avoidance
- Per-model display control: `display_field` / `display()` for relation labels
- **Hierarchy tree** — render a record inside a parent→children tree
  (`tree_parent` / `tree_children`), always from the topmost ancestor. Children
  load **lazily** as searchable, paginated mini-tables (scales to thousands of
  relations), with per-row permission-aware View / Edit / Delete
- **Menu views** — admin-defined, named subsets of the sidebar (which models, and
  which of their fields), switchable from the top bar; always narrowed by perms
- **Favorites** — each user stars their own home-page shortcuts (server-side,
  per user; intersected with what they may see)
- **Per-user personalization** (server-side, follows the user across devices):
  **UI language** (9 built-in languages, runtime-translated), **dark / light /
  auto theme**, timezone, and **drag-to-reorder** the sidebar (app groups +
  models) and home favorites — with a one-click "Reset order"
- **Settings page** — per-user preferences plus, for superusers, **admin overrides
  of the deploy config** (site title, logo, schema-cache TTL, cache version) with
  a reset-to-`settings.py` and a manual **schema-cache flush**
- **Configurable brand logo** before the title (a static path or any URL)
- Session login built into the SPA, gated by the `theia_ng.access` permission
- **Responsive** throughout: collapsible sidebar (full → compact initials rail →
  off-canvas drawer on mobile), scrollable tables; a per-user greeting in the bar
- Sidebar grouped by Django app; **app names link to a per-app landing page** of
  their model cards; sticky top bar with a settings gear and sign-out
- Optional **admin.py discovery** — reuse existing `django.contrib.admin`
  registrations (incl. **fieldsets, list_editable, inlines**) via `DISCOVER_ADMIN_FILES`
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

**4. Migrate** (creates the `theia_ng.access` permission and Theia's own tables —
`MenuView` for sidebar views, `UserSettings` for per-user preferences, `SiteConfig`
for admin config overrides — run this after upgrading too):

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
    "LOGO_URL": "img/logo.png", # logo before the title; a static path (resolved
                                # via static()) or any absolute URL / data: URI
    "MOUNT_PREFIX": "/theia/",  # usually auto-detected from the request
    "SCHEMA_TTL": 300,          # IR cache TTL in seconds (0 disables caching)
    "CACHE_VERSION": "1",       # bump to invalidate the IR cache on deploy
    # List rows auto-select_related the forward relations their labels traverse
    # (kills N+1); on by default, set False to disable.
    "AUTO_SELECT_RELATED": True,
    # Optional fast list path — a swappable provider that serializes list pages
    # in bulk instead of per row. Unset = generic per-instance path (default).
    # "LIST_PROVIDER": "fastberry.list_provider.ListProvider",
}
```

`SITE_TITLE`, `LOGO_URL`, `SCHEMA_TTL` and `CACHE_VERSION` are **overridable at
runtime from the Settings page** (superusers): the override is stored in the
`SiteConfig` row and layered over `settings.py`, with a one-click reset back to
these values and a button to flush the schema cache. `LIST_PROVIDER` and
`MOUNT_PREFIX` are structural and stay deploy-only. See
[Personalization & settings](#personalization--settings).

By default the list endpoint inspects each model's relation labels — the row's
`__str__`, computed `@display` columns, and every FK's target `__str__`
(or `display_field`) — and `select_related`s the forward-relation paths they
reach, so a list never does a per-row N+1 for labels. It only follows forward
FK/O2O hops (never reverse/M2M) and the output is unchanged. You can still add
explicit `list_select_related` on a `ModelAdmin`; set
`THEIA_NG['AUTO_SELECT_RELATED'] = False` to turn the automatic behaviour off.

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

### Descriptions & hints

Set **`description`** for a short blurb shown under the title on a model's list
and detail pages; field-level `help_text` from the model renders as a small hint
under each field:

```python
@theia_ng.register(Article)
class ArticleAdmin(theia_ng.ModelAdmin):
    description = "Public articles, drafted then published by editors."
```

## Fieldsets

Group form fields into sections (django-admin's `fieldsets`). A `"collapse"`
class makes the section collapsible (collapsed by default); fields you don't list
still render (so a required-on-create field is never hidden):

```python
@theia_ng.register(Article)
class ArticleAdmin(theia_ng.ModelAdmin):
    fieldsets = [
        (None, {"fields": ["title", "category", "body"]}),
        ("Advanced", {
            "fields": ["slug", "internal_notes"],
            "classes": ["collapse"],
            "description": "Rarely changed.",
        }),
    ]
```

## Inline editing in the list (`list_editable`)

Make non-relation columns editable in place on the list. They must also be in
`list_display`; a save bar commits all edited rows at once, and a row click still
opens the record:

```python
@theia_ng.register(Stock)
class StockAdmin(theia_ng.ModelAdmin):
    list_display = ["title", "quantity", "is_active"]
    list_editable = ["quantity", "is_active"]
```

## Inlines

Edit a parent's related child rows right on its form (django-admin's inlines).
Subclass `theia_ng.Inline`, point it at the child model, and list it in the
parent's `inlines`. The child's foreign key back to the parent is auto-detected
(set `fk_name` if ambiguous) and filled in on save; rows are created / updated /
deleted in the **same transaction** as the parent (an invalid child rolls the
whole save back):

```python
class ItemInline(theia_ng.Inline):
    model = OrderItem
    fields = ["product", "qty", "price"]   # the parent FK is excluded
    extra = 1                              # blank rows offered for adding
    style = "tabular"                      # "tabular" (grid) | "stacked"
    # can_delete, readonly_fields, exclude, raw_id_fields, fk_name also supported

@theia_ng.register(Order)
class OrderAdmin(theia_ng.ModelAdmin):
    inlines = [ItemInline]
```

Each inline cell reuses the normal field widgets, so child FK / choice / boolean
fields edit exactly like the main form. Tabular inlines lay rows out as a grid
(labels become column headers); stacked inlines render each row as a labelled
block.

## Personalization & settings

A **Settings page** (gear icon in the top bar) holds:

- **Per-user preferences** — UI **language** (English, Hungarian, German, French,
  Chinese, Korean, Russian, Spanish, Turkish), **theme** (dark / light / auto,
  following the OS), and **timezone**. Stored server-side per user (they follow
  the user across devices); the defaults come from Django (`get_language()`,
  `TIME_ZONE`). Dates and numbers render in the chosen locale and timezone.
- **Site settings** (superusers) — override `THEIA_NG['SITE_TITLE']`, `LOGO_URL`,
  `SCHEMA_TTL` and `CACHE_VERSION` from the UI; each shows its `settings.py`
  default as a hint, with a **Reset to defaults** that drops the override.
- **Maintenance** (superusers) — **Clear schema cache**, flushing the cached IR
  immediately (without bumping `CACHE_VERSION`).

The sidebar (app groups and the models within them) and the home favorites are
**drag-to-reorder** (a handle on each item; the rest of the row still navigates),
saved per user, with a **Reset order** control to restore the default ordering.

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
view from a button in the top bar that opens a picker dialog (an icon-only button
on mobile); "Full" (everything permitted) is always available.

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

## Hierarchy tree

Show a record inside a parent→children tree — e.g. a multi-tenant
`Registration → Company → House → Space` hierarchy. Each model declares the
forward FK up to its parent (`tree_parent`) and the reverse accessors down to
its children (`tree_children`):

```python
@theia_ng.register(Registration)
class RegistrationAdmin(theia_ng.ModelAdmin):
    tree_children = ["companies"]          # reverse accessor (related_name)

@theia_ng.register(Company)
class CompanyAdmin(theia_ng.ModelAdmin):
    tree_parent = "registration"
    tree_children = ["houses"]

@theia_ng.register(House)
class HouseAdmin(theia_ng.ModelAdmin):
    tree_parent = "company"
    tree_children = ["spaces"]

@theia_ng.register(Space)
class SpaceAdmin(theia_ng.ModelAdmin):
    tree_parent = "house"                   # leaf
```

Any model with `tree_parent` and/or `tree_children` gets a **Hierarchy** button
on its detail page. The tree always renders from the **topmost ancestor**,
regardless of which level you opened it from (open it on a `Space` and you still
see the whole `Registration` tree, with the lineage auto-expanded down to that
`Space` and highlighted).

Children **load lazily**: each node shows its child relations as collapsed
groups with a count; expanding one fetches a **searchable, paginated mini-table**
(server-side search over the child's `search_fields`, page size = its
`list_per_page`). Nothing is loaded until you open it, so a node with thousands
of children stays fast. A child group is hidden entirely if the user can't view
that model. `tree_children` uses Django's reverse accessor names (the
`related_name`, or the default `<model>_set`).

### Compact hierarchy

The detail page also offers a collapsible **compact** hierarchy: instead of
lazy mini-tables it builds the **whole** tree (from the topmost ancestor, every
descendant) in a single eager request and renders it as a simple indented table,
with a single permission-based action per row (Edit if you may change it, else
View) and no delete. The opened record is marked *(this record)*.

### `@compact_tree` field

To embed a compact tree **among the form fields** (independent of the page
section above), decorate a method that returns the object to root it at, and drop
its name into `fields` / `fieldsets` like any field. It is read-only, roots at
the returned object's **own descendants**, and is hidden when the method returns
`None`:

```python
@theia_ng.register(House)
class HouseAdmin(theia_ng.ModelAdmin):
    fieldsets = [(None, {"fields": ["name", "company", "structure"]})]

    @theia_ng.compact_tree(description="Structure")
    def structure(self, obj):
        return obj            # this House's spaces/stocks
        # return obj.company  # ...or root higher up
```

## Parameterized actions

A plain action runs over a selection: `method(request, queryset)`. A
*parameterized* action also pops a small form — declare it with
`@theia_ng.action` and it receives the collected values as a third `params`
dict. `selection` controls whether it needs selected rows: `"required"`
(default), `"optional"`, or `"none"` (a global action, e.g. a broadcast):

```python
@theia_ng.register(Message)
class MessageAdmin(theia_ng.ModelAdmin):
    actions = ["broadcast"]

    @theia_ng.action(
        label="Broadcast message",
        selection="none",                       # ignores row selection
        fields=[
            theia_ng.ActionField("body", "text", label="Message", required=True),
            theia_ng.ActionField("to_all", "boolean", label="All active users"),
            theia_ng.ActionField("recipients", "m2m", relation="users.customuser"),
            theia_ng.ActionField("send_push", "boolean", label="Send push"),
        ],
    )
    def broadcast(self, request, queryset, params):
        recipients = (
            User.objects.filter(is_active=True) if params["to_all"]
            else User.objects.filter(pk__in=params["recipients"], is_active=True)
        )
        Message.objects.bulk_create([...])
        return {"sent": recipients.count()}
```

`ActionField` types reuse the IR field types (`string`, `text`, `integer`,
`decimal`, `boolean`, `choice`, plus `fk` / `m2m` with `relation="app.model"`
for a searchable picker). The SPA renders the form with the same widgets as the
record form and validates `required` fields server-side. Selection-less (`none`)
actions are toolbar buttons; selection-driven ones appear in the bulk bar below.

### Object (detail) actions

`detail=True` makes an action run on a **single record** and show up as a button
on that record's **detail page** (not in the list's bulk bar) — the equivalent of
a custom button on django-admin's change page. The `queryset` it receives holds
just that one record; its `fields` are the inputs *beyond the record itself*
(e.g. a copy target). `dangerous=True` adds a confirm step.

```python
@theia_ng.register(House)
class HouseAdmin(theia_ng.ModelAdmin):
    actions = ["copy_stocks", "clear_modules"]

    @theia_ng.action(
        label="Copy stock(s) to house",
        detail=True,                              # button on the House page
        fields=[theia_ng.ActionField("target", "fk", relation="structure.house",
                                     required=True)],
    )
    def copy_stocks(self, request, queryset, params):
        source = queryset.first()                 # the open record
        ...

    @theia_ng.action(label="Clear modules", detail=True, dangerous=True)
    def clear_modules(self, request, queryset, params):
        queryset.first().modules.clear()
```

The detail buttons sit below the record title and wrap onto new rows when they
don't fit.

## Bulk actions & row selection

The list has row checkboxes and a bulk action bar (django-admin style), on by
default. Toggle per model with `list_selectable`:

```python
@theia_ng.register(Stock)
class StockAdmin(theia_ng.ModelAdmin):
    list_selectable = True          # default; set False to hide checkboxes
    actions = ["deactivate"]        # selection-driven actions show in the bulk bar

    def deactivate(self, request, queryset):
        return {"updated": queryset.update(is_active=False)}
```

- A built-in **"Delete selected"** action is always available (gated on delete
  permission); your `actions` with selection `"required"`/`"optional"` join it in
  the bar.
- The header checkbox selects every row **on the page**. When a page is fully
  selected, a banner offers **"Select all N"** — running the action then operates
  on every record matching the current filters/search (the server rebuilds that
  queryset from the same filters; it isn't sent a giant id list).
- Dangerous actions (like delete) confirm first. Actions are gated on the
  permission they need (`change` for custom actions, `delete` for the built-in).

## Audit log

Every write through Theia NG (create / update / delete / action) is recorded as
a `LogEntry`: who, when, which model + object, and — for create/update — a
field-level diff (`{field: [old, new]}`, audit-noise fields excluded). It is
best-effort, so logging never breaks the operation it records.

The **Activity** page (linked from the sidebar and the home "Theia NG Admin"
section) lists the entries, filterable by action and model. Regular users see
only their own trail; superusers see everyone's and can filter by user. No
configuration needed — it follows from `migrate`.

## Discovering existing `admin.py`

If your project (or a third-party package) already configures models with
`django.contrib.admin`, Theia NG can reuse that — set:

```python
THEIA_NG = {"DISCOVER_ADMIN_FILES": True}
```

On startup, after your `theia.py` registrations, Theia imports every app/package
`admin.py` and, for each model **not already registered with Theia**, builds a
`ModelAdmin` from the *compatible* subset of the Django admin's options.

Copied (same meaning in both): `list_display` (real fields + `a__b` lookups
only), `list_filter` (plain field-name filters only), `search_fields`,
`ordering`, `list_per_page`, `readonly_fields`, `exclude`, `raw_id_fields`,
`fields` (flat lists), `list_select_related` (when an explicit list),
**`fieldsets`**, **`list_editable`**, and **`inlines`** (`TabularInline` /
`StackedInline`, mapped to `theia_ng.Inline`).

Dropped (Django-specific / not portable): callable or admin-method `list_display`
columns, `SimpleListFilter` classes, `actions`, custom widgets, `date_hierarchy`,
`autocomplete_fields`, etc. A discovered model renders with safe defaults rather
than broken columns. Explicit `theia.py` registrations always win, and one broken
`admin.py` never breaks the rest.

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

## Optional: fast list provider

The list endpoint serializes one model instance per row by default. For large or
hot lists you can plug in a **list provider** that builds the whole page from
column-projected queries instead — no per-row instances.

A ready-made one is [**fastberry**](https://pypi.org/project/fastberry/): its
`ListProvider` compiles each list into a column-projected schema (FK labels via a
join, M2M set-based over the through table) and encodes the page in one go —
typically several times faster on large/relational lists. To use it:

```bash
pip install fastberry
```

```python
THEIA_NG = {"LIST_PROVIDER": "fastberry.list_provider.ListProvider"}
```

Theia core has **no dependency** on any provider — the dotted path is the only
coupling, and the provider is fully swappable (fastberry is just the reference
implementation). A model is only accelerated when its labels are DB-expressible
(its admin, and every relation target's admin, set `display_field`); otherwise
that model transparently uses the generic path, so output is identical either
way. When `LIST_PROVIDER` is unset there is no fast path at all.

Want to back it with something else (raw `.values()`, a SQL view, a non-Django
store)? Writing a provider is one method. See
**[docs/list_provider.md](docs/list_provider.md)**.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for the per-release history.

## License

MIT — see [LICENSE](LICENSE).
