# Changelog

All notable changes to **Theia NG** are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and the project follows
[Semantic Versioning](https://semver.org/).

## [0.22.0] — 2026-06-27
### Added
- **Icons reach the relation widgets.** The FK/M2M relation widget and the raw_id
  picker buttons (View / Edit / Delete / Remove link / Delete entity / Choose) now
  honour the per-user button display preference (label / icon / both).

### Changed
- **Dialogs use an X close control.** The textual *Cancel* button is replaced by a
  small **✕** in the dialog's top-right corner (action, confirm, filter, relation
  picker and the relation delete dialogs).
- **Destructive action sits on the right.** In dialogs the delete/destructive
  button is right-aligned while the others stay left (e.g. *Delete entity* right,
  *Remove link* left; a confirm dialog's *Delete* goes right).
- Localized the previously hardcoded **Add filter** title and the relation
  picker's **Choose / N selected** header.

## [0.21.0] — 2026-06-27
### Added
- **Per-user button display preference.** A new *Buttons* setting — **Label**
  (default), **Icon**, or **Label + icon** — stored per user and applied via
  `<html data-btn>`. A curated set of buttons (Save, Save & continue, Cancel,
  Edit, Delete, Back, Add, Filter) gained icons through the new `theia-blabel`;
  in icon-only mode the label stays in the accessibility tree.
  **Requires a migration** (`0008`, a `button_style` column on `UserSettings`).

### Changed
- **Larger, responsive dialogs.** The cramped confirm/relation/picker dialogs got
  more room and now clamp to the viewport (max-width / max-height with scroll).
- **Compact `@compact_tree` field polish.** It no longer repeats the section
  title as a field label, and its row action button is outline like the others
  (was filled).

## [0.20.0] — 2026-06-26
### Changed
- **The compact hierarchy is now opt-in via `@compact_tree` only.** The automatic
  collapsible hierarchy section on the detail page was removed — a model shows a
  compact tree only where a `@compact_tree` field is declared and placed. (The
  lazy **Hierarchy** page link, from `tree_parent`/`tree_children`, is unchanged.)

### Added
- **`tree-full ?current=<key>:<pk>`** so a `@compact_tree` field rooted at an
  ancestor still flags the page's actual record as *(this record)*, not the root.

## [0.19.0] — 2026-06-26
### Added
- **`@theia_ng.compact_tree` — a placeable hierarchy field.** Decorate a method
  that returns the object to root at, then drop its name into `fields` /
  `fieldsets`: it renders that object's eager subtree (descendants) as a
  read-only, indented table among the form fields, independent of the page's
  full-hierarchy section. Returns `None` to hide it. Backed by `tree-full`'s new
  `?root=self` mode (root at the record instead of climbing to the ancestor).

### Changed
- **Fieldsets restyled.** Titled form sections now render as a clean heading with
  a divider and the fields beneath — matching the compact-tree look — instead of
  a heavy bordered box wrapping the whole section.

## [0.18.0] — 2026-06-26
### Added
- **Compact hierarchy on the detail page.** A collapsible *Hierarchy* section on
  any tree-enabled record builds the **whole** hierarchy — rooted at the topmost
  ancestor, every descendant expanded — in a single eager request (no lazy
  per-node loading), rendered as a simple indented table. The opened record is
  flagged *(this record)*; there is no delete here. Backed by a new
  `tree-full/<key>/<pk>/` endpoint (`build_full_subtree`, capped at 2000 nodes).
- **Tooltips on the Home page** for the favorite stars (add/remove) and the model
  cards (*Open {name}*); the reorder handle already had one.

### Changed
- **One permission-based action instead of a View/Edit pair.** Tree nodes, the
  raw_id FK widget and the relation widget now show a single button — **Edit**
  when you have change permission, otherwise **View** — instead of both.
- **Relation delete is clearer.** The relation widget's delete prompt now spells
  out the difference between **Remove link** (unlinks only — the record stays) and
  **Delete entity** (permanently deletes the record), so the two roles aren't
  confused. Confirm dialogs gained an optional hint line for the same purpose.

### Fixed
- **Delete dialog fully translated.** The confirmation dialog now falls back to
  translated labels when a caller omits one (its **Cancel** button was showing in
  English), and the relation widget's delete prompt — previously hardcoded
  English — is localized across all 9 languages.

## [0.17.1] — 2026-06-26
### Fixed
- **Inlines now refresh after a save or custom action.** The inline editor only
  seeded its rows once (on init), so after the detail page reloaded — e.g.
  following a detail action like *Add / remove module group*, or a normal save —
  the inline kept showing stale rows and the change didn't appear. It now
  re-seeds whenever the parent passes fresh rows on reload, while leaving
  in-progress edits untouched (the parent only swaps the array on reload, not
  while you type).
- **An inline relation can't be assigned twice.** A to-one (FK) field in an
  inline now hides the values already chosen in its other rows — including the
  already-saved ones — so e.g. the same Module can no longer be added to a House
  on two rows. Implemented as a generic `exclude` on the relation dropdown
  (relation select → field → inline editor); the row's own current selection is
  never hidden.

## [0.17.0] — 2026-06-24
### Fixed
- **Search no longer duplicates rows across to-many relations.** When
  `search_fields` (or a `list_filter`) spans a reverse FK / M2M, the join emitted
  one row per related match, so a record could appear many times (e.g. a user
  shown once per registration). The list and the relation-option search now apply
  `.distinct()` whenever a lookup spawns duplicates — mirroring Django admin —
  while to-one lookups (local fields, forward FKs) stay join-free and unaffected.

### Changed
- **Fully localized UI chrome.** Action buttons and labels that were still
  hardcoded English — **View / Edit / Delete / Run / OK / Apply / Cancel /
  Choose… / Remove link / Delete entity**, plus the relation picker's
  placeholders (Add… / Select… / No matches…) and the hierarchy tree's controls —
  now go through the runtime i18n dictionary in all **9 languages**. The built-in
  **Delete selected** bulk action is translated by key, while custom (app-defined)
  actions keep their own server label.

## [0.16.2] — 2026-06-20
### Added
- **View / Edit shortcuts on raw_id FK fields.** A `raw_id_fields` FK shows just
  the id (great for huge tables), but now — when it has a value and its target is
  registered — **View** and **Edit** buttons appear before **Choose…**, so you
  can jump straight to the related record instead of hunting for it. Same
  permission gating as the normal relation widget (View needs `view`, Edit needs
  `change`); shown for FK only (not multi-valued raw M2M).

## [0.16.1] — 2026-06-20
### Changed
- **List loading is now skeleton-only.** The list dropped the floating loading
  pill/spinner; instead the skeleton placeholder takes over on **every** page
  load (not just the first). Each skeleton row is a single bar spanning the whole
  row. On page change the stale rows (and their PKs) no longer linger under a
  spinner — they're replaced by the skeleton immediately, then refreshed with the
  new page. (The detail page and the top-bar still use the pill/spinner.)

## [0.16.0] — 2026-06-20
### Added
- **Skeleton loaders** — the list (first page) and the home cards show a subtle
  shimmer placeholder while loading, instead of an empty flash.

### Fixed
- **Inline relation fields** now open the modal "Choose…" picker instead of the
  inline dropdown panel, which a tabular inline's horizontal scroll could clip.
- **Sidebar "Activity" link** had lost its indentation (sat flush-left, looking
  like it left the admin group) after the reorderable-nav change — it's aligned
  with the other group items again.

## [0.15.0] — 2026-06-20
### Added
- **Object (detail) actions** — `@theia_ng.action(detail=True)` marks an action
  that runs on a **single record** and appears as a button on that record's
  **detail page** (instead of the list's toolbar / bulk bar). Its `fields` are the
  inputs *beyond the record itself* (e.g. a copy target), collected in the usual
  action form; `dangerous=True` adds a confirm step. This mirrors django-admin's
  per-object change-page buttons. The buttons sit below the record title and wrap
  onto new rows when they don't fit.

## [0.14.0] — 2026-06-20
### Added
- **Settings page** (gear icon in the top bar). Per-user preferences — UI
  **language**, **theme**, and **timezone** — moved here from the top bar (the
  sticky bar no longer carries the language/theme selectors).
- **Admin overrides of the deploy config.** Superusers can override
  `THEIA_NG['SITE_TITLE']`, `LOGO_URL`, `SCHEMA_TTL` and `CACHE_VERSION` from the
  Settings page; the override is stored in a new `SiteConfig` singleton and
  layered over `settings.py` everywhere config is read (cache keys, topbar
  title/logo, injected SPA config). Each field shows its `settings.py` default as
  a hint, with a one-click **Reset to defaults**. Migration `0007`.
- **Manual schema-cache flush** — a "Clear schema cache" button (superusers)
  invalidates the cached IR immediately by bumping a cache generation folded into
  the cache key, without touching `CACHE_VERSION`.
- **Live brand updates** — editing the site title/logo updates the topbar (and
  home heading) immediately, no reload.
- **`LOGO_URL` accepts a static path** — a bare path like `admin/imgs/logo.png` is
  resolved via Django `static()`; absolute URLs / `data:` URIs pass through.

### Changed
- The **menu-view selector** is now a top-bar **button that opens a picker dialog**
  instead of a `<select>`.
- **Mobile top bar**: the version footnote is hidden and the view-picker collapses
  to an icon-only button.

## [0.13.1] — 2026-06-19
### Added
- **"Reset order"** control at the bottom of the sidebar — restores the default
  (name) ordering by clearing the saved app-group and per-group model order. Only
  shown when a custom order exists. Translated in all 9 languages.

### Fixed
- **Dark theme polish.** Several surfaces were hardcoded light and broke in dark
  mode: dialogs (now `var(--panel)`/`var(--text)` — previously near-invisible),
  form inputs/selects/textareas, search boxes, the relation picker panel/trigger
  and option rows, secondary/plain buttons, log-filter selects, and chips. The
  list **row hover** was a glaring near-white in dark mode; it now uses a subtle,
  theme-aware accent tint (`--hover`).

## [0.13.0] — 2026-06-19
### Added
- **Inlines** (`theia_ng.Inline`, `TabularInline`/`StackedInline` style) — edit a
  parent's related child rows on its form. List inline classes in a ModelAdmin's
  `inlines`; the child's FK back to the parent is auto-detected and set on save.
  Existing rows load with the detail record; add/update/delete happen in the same
  transaction (invalid children roll the whole save back). Closes the largest
  django-admin gap (inlines were previously dropped on discovery).
- **fieldsets** — group form fields into sections with an optional heading,
  description and `collapse` class (collapsible, collapsed by default). Fields not
  named in any fieldset still render (never hidden), so required-on-create fields
  are safe.
- **list_editable** — edit cells directly in the list (non-relation columns that
  are also in `list_display`). A save bar commits all edited rows at once; row
  clicks still open the record.
- **Discovery** now translates django admin `fieldsets`, `list_editable` and
  `inlines` (`TabularInline`/`StackedInline`) too, not just the flat field options.
- **Per-user settings** model + `GET/PATCH /api/settings/` endpoint. Persists
  language, timezone, theme and sidebar order per user (one row, like
  `Favorite`); blanks fall back to Django's defaults (`get_language()`,
  active timezone), which the endpoint fills in on read. Migration `0006`.
- **UI translation (i18n).** All UI chrome is translated at runtime from a
  dictionary keyed by language (single prefix-independent bundle — no
  `$localize`), shipping **9 languages**: English, Hungarian, German, French,
  Chinese, Korean, Russian, Spanish, Turkish. A language switcher in the topbar;
  the default follows Django's active language. Missing keys fall back to English.
- **Locale + timezone-aware dates.** List/log datetimes are formatted with `Intl`
  in the user's locale and timezone (replacing naive ISO string slicing); plain
  dates are not timezone-shifted.
- **Configurable brand logo** before the topbar title, from `THEIA_NG['LOGO_URL']`
  (injected config + registry `site` payload). Rendered in a fixed-height slot
  with `object-fit: contain`, so it never resizes the sticky bar and its aspect
  ratio is preserved.
- **Dark / light / auto theme.** A topbar switcher; `auto` follows the OS
  `prefers-color-scheme`. Saved per user and applied before first paint (an
  inline bootstrap reads the saved preference) to avoid a flash. Implemented with
  a `[data-theme]` dark CSS-variable set.
- **Reorderable sidebar nav + home favorites** via drag-and-drop (`@angular/cdk`),
  two levels: **app groups** reorder as a whole block (handle on the app header,
  saved as `nav_app_order`) and **models reorder within their app** (handle on
  each item, saved as `nav_order`). A drag handle on the right is the only grab
  target — clicking it doesn't navigate; clicking elsewhere on the row still does.
  Dragging is locked to the vertical axis and bounded to the sidebar, and the
  drag preview renders in place (no flying/misplaced clone). Home **favorites**
  reorder within their grid. All orders are saved per user.

### Fixed
- **Bulk action / delete count in the activity log.** The log UI counted
  `changes.ids`, which `delete_selected` (and any select-all-matching action)
  never records, so it showed "0 object(s)". Actions now record an authoritative
  `count` and the UI prefers it (with an "(all matching)" hint), falling back to
  `ids` for older entries.

## [0.12.1] — 2026-06-19
### Fixed
- The bulk **Apply button did nothing** — under zoneless change detection, the
  action `<select>` value isn't reactive, so the button's enabled state and the
  chosen action were stale. The dropdown is now bound to a signal.

## [0.12.0] — 2026-06-19
### Added
- **Row selection + bulk actions** in the list (django-admin style):
  - row checkboxes and a header "select all on this page" checkbox;
  - a **bulk action bar** to run a selection-driven action over the checked rows;
  - a built-in **"Delete selected"** action (gated on delete permission), plus any
    `ModelAdmin.actions` with a `required`/`optional` selection mode;
  - **"Select all N matching"** — when a page is fully selected, a banner offers to
    operate on every record matching the current filters/search, not just the page;
    the server rebuilds that queryset from the same filters (`{"all": true,
    "filters": {…}}`) instead of receiving a huge id list;
  - toggle per model with `ModelAdmin.list_selectable` (default `True`).
  Custom actions advertise the permission they need (`requires`) and whether they
  need a confirm step (`dangerous`); the SPA hides/guards them accordingly.

## [0.11.6] — 2026-06-19
### Fixed
- **Stale-response race on navigation.** Opening a slow list/detail and then
  switching to another model (or record) before it loaded could let the late
  response overwrite the page you'd moved to. In-flight schema/list/retrieve
  requests are now cancelled (XHR aborted) on navigation and on re-load, so only
  the current view's response is applied.

## [0.11.5] — 2026-06-19
### Changed
- **Pager (prev/next) buttons** now follow the secondary-button convention
  (panel background, accent text, rounded border, hover + disabled states)
  instead of raw browser buttons. Applies to every pager (list, relation picker,
  logs).
- The **topbar version footnote is now also sourced from the live registry API**
  (`/schema/`), not only the injected index config — so it shows the real version
  even if a cached `index.html` predates the field.

## [0.11.4] — 2026-06-19
### Added
- **Global "server busy" spinner** in the topbar (before Sign out): a small
  spinner appears whenever any HTTP request is in flight (tracked via an HTTP
  interceptor that counts in-flight requests), so the user can tell the server is
  working or a component is awaiting a response. It sits in a fixed-size slot, so
  the topbar never changes size.

## [0.11.3] — 2026-06-19
### Fixed
- `theia_ng.__version__` was hardcoded (stuck at an old value) instead of
  tracking the installed distribution. It now reads the package metadata, so the
  topbar version footnote shows the real version and — since `cache.py` uses
  `__version__` as the default `CACHE_VERSION` — the IR cache key actually changes
  across upgrades instead of being frozen.

## [0.11.2] — 2026-06-18
### Added
- The **pk column is now sortable** in the list view.
### Changed
- When a `ModelAdmin` declares no `ordering`, the list now defaults to **pk
  descending** (newest first) instead of pk ascending.

## [0.11.1] — 2026-06-18
### Added
- **Loading indicator on the detail view** — a spinner pill while a single
  record's schema + data fetch, instead of a blank screen.
### Fixed
- The list loading overlay no longer looks cut off on an empty result: the table
  area keeps a min-height while loading so the spinner pill is fully visible.

## [0.11.0] — 2026-06-16
### Changed
- **List rows are now scoped to the shown columns.** Previously a list row
  serialized *every* concrete field (and every FK as a `{id,label}` cell);
  now it serializes only the pk, the `__str__` label, and the columns actually
  shown — the admin's `list_display`, or the `columns=` the client sends for a
  saved view. This narrows the query (only shown FKs are joined) and shrinks the
  payload dramatically (e.g. a wide model dropped from ~35 keys/1.1 kB per row to
  ~5 keys/170 B). `select_related` and the fastberry fast path are scoped to the
  same columns. The detail endpoint still returns all fields. **Note for direct
  API consumers:** request the fields you need via `?columns=a,b,c` (the bundled
  SPA does this automatically); without it, the row contains `list_display`.

## [0.10.2] — 2026-06-16
### Added
- The installed **package version is shown in the topbar** as a small footnote
  after the site title (injected into the SPA runtime config).
### Changed
- The list **loading indicator** is now a pill pinned near the top of the
  viewport (`position: sticky`) instead of a centred overlay, so it no longer
  slips out of view on tall pages.

## [0.10.1] — 2026-06-16
### Added
- **Loading indicator on the list view.** While a list page fetches, a spinner
  overlay covers the table (and the "No records." empty state is suppressed), so
  a slow request reads as "loading" instead of "already updated but empty" — the
  list navigation syncs the URL (which scrolls to top) before the data arrives.

## [0.10.0] — 2026-06-15
### Added
- **Automatic `select_related` for list rows** (`THEIA_NG['AUTO_SELECT_RELATED']`,
  on by default). The list endpoint inspects each model's relation labels — the
  row's `__str__`, computed `@display` columns, and every FK target's `__str__`
  (or `display_field`) — and `select_related`s the forward-relation paths they
  traverse, eliminating per-row label N+1s with no change to output. Only forward
  FK/O2O hops are followed (never reverse/M2M); results are cached per model.
  Explicit `ModelAdmin.list_select_related` still applies and merges on top.

## [0.9.0] — 2026-06-15
### Added
- **Pluggable list provider** (`THEIA_NG['LIST_PROVIDER']`) — an optional fast
  path that serializes a list page in bulk from column-projected queries instead
  of per instance. theia core has no dependency on any provider; the dotted path
  is the only coupling and it is fully swappable. A model is accelerated only when
  its labels are DB-expressible — its admin, and every relation target's admin,
  set `display_field` — otherwise it transparently uses the generic path, so
  output is identical. When `LIST_PROVIDER` is unset there is no fast path.
  `fastberry.list_provider.ListProvider` is a ready-made reference implementation.
  See [docs/list_provider.md](docs/list_provider.md).
### Changed
- Relation labels (FK / M2M in list rows and detail) now come from the target
  `ModelAdmin.display()` (which honours `display_field`, falling back to `str()`),
  unifying labels across list rows and relation pickers. Backward-compatible where
  no `display_field` is set.
- `ModelAdmin` detail M2M can be capped via `THEIA_NG['DETAIL_M2M_CAP']`
  (default `None` = uncapped, unchanged behaviour).

## [0.8.0] — 2026-06-15
### Added
- **`admin.py` discovery** (opt-in via `THEIA_NG['DISCOVER_ADMIN_FILES']`) —
  reuse existing `django.contrib.admin` registrations across apps and installed
  packages: for each model not registered with theia, a `ModelAdmin` is built
  from the compatible subset of options (field-based config), dropping
  Django-specific pieces (method columns, `SimpleListFilter`, actions, inlines,
  …). Explicit `theia.py` wins; one broken `admin.py` never breaks the rest.
### Fixed
- The MenuView field-picker skips groups for models that are no longer
  registered/accessible (stale favorites and menu-view keys never error).

## [0.7.3] — 2026-06-13
### Changed
- PEP 639 license metadata: SPDX `license = "MIT"` + `license-files`; dropped the
  redundant `License :: OSI Approved :: MIT License` classifier (cosmetic;
  `Metadata-Version: 2.4`).

## [0.7.2] — 2026-06-13
### Performance
- Lists serialize only the displayed columns; a non-displayed M2M is never
  prefetched or materialized per row, and a displayed M2M is capped (`+N more`).
  New `DataAdapter.to_list_representation` (generic adapter is light; DRF keeps
  full).
- Relation-picker options serialize `pk` + label only (scalars/FK), never M2M.

## [0.7.1] — 2026-06-13
### Fixed
- `site_title` now reads `THEIA_NG['SITE_TITLE']`, so the registry payload and the
  SPA config share one source — the top bar no longer falls back to the hardcoded
  default while the home page showed the configured title.

## [0.7.0] — 2026-06-13
### Added
- **Toast notifications** for every operation (top-right, auto-dismiss; green
  success, longer-lived red error with a close button).
- **raw_id fields** get a modal table picker — searchable, paginated, loads only
  on open, pre-selects current assignments by pk, and uses the unfiltered list so
  even unmatched/bad assignments stay listable.
- **`list_select_related` / `list_prefetch_related`** on `ModelAdmin` to avoid
  N+1 for cross-relation labels.
- **Save and continue editing**; detail form lays out Save / Save and continue /
  Cancel on the left, Delete pushed to the far right.

## [0.6.1] — 2026-06-13
### Added
- **Relation-spanning lookups** (`a__b__c`) in `list_display` / `list_filter`:
  labelled, sortable, filterable, with `select_related` optimization.
- **Date filters** with relative presets (today, last 2 / 7 / 30 days, last year)
  or a specific day (time optional); locale-aware date rendering in lists.
### Changed
- Delete confirmation is a modal, not the browser `confirm()` alert.
- The filter dialog rejects empty values.

## [0.6.0] — 2026-06-12
### Added
- **Parameterized actions** — `@theia_ng.action` + `ActionField` declare a form
  (text, choices, FK/M2M relation pickers); `selection` of `none` / `optional` /
  `required`; the SPA renders the form as toolbar buttons.
- **Audit log** — `LogEntry` records every create / update / delete / action with
  a field-level diff; an Activity page (own trail; superusers see everyone's).
- **App landing pages** — clicking a sidebar app name opens a card page of that
  app's models.
- Per-user greeting + email in the top bar; the title links home.

## [0.5.0] — 2026-06-12
### Added
- **Favorites** — per-user, server-side home-page shortcuts.
- **Responsive** shell: collapsible sidebar (full → compact initials rail →
  off-canvas mobile drawer), scrollable tables.

## [0.4.1] — 2026-06-12
### Added
- **Hierarchy tree** — render a record inside a parent→children tree
  (`tree_parent` / `tree_children`), always from the topmost ancestor; children
  load lazily as searchable, paginated mini-tables.

## [0.4.0] — 2026-06-12
### Added
- **Home dashboard** — model cards grouped by app, with a shared `groupByApp`
  helper.

## [0.3.0] — 2026-06-12
### Added
- **Menu views** — admin-defined named sidebar subsets (which models, and which
  of their fields), switchable from the top bar; always narrowed by permissions.
- **Custom list filters** — `theia_ng.ListFilter` (a `SimpleListFilter`
  equivalent), mixable with field-name filters.

## [0.2.0] — 2026-06-12
### Added
- Richer relation UI: M2M selections shown as a table above the picker;
  permission-aware View / Edit / Delete on relation rows; breadcrumbs +
  context-aware Back; list state (search / filter / page) in the URL.
- `ModelAdmin`: computed `list_display` columns + `@theia_ng.display`,
  `readonly_fields` (shown-but-disabled), `exclude`, `raw_id_fields`,
  `display_field` / `display()`, and a `get_queryset` hook scoping list + detail.

## [0.1.2] — 2026-06-11
### Added
- **Dependent relation options** — `relation_filters` narrows a relation field's
  options by sibling field values (server-defined lookups; the combobox re-fetches
  on change).

## [0.1.1] — 2026-06-11
### Fixed
- M2M relation picker no longer loses selections (chips in the trigger are
  display-only; the dropdown closes via an outside-click listener).

## [0.1.0] — 2026-06-10
### Added
- Initial release: auto-CRUD (list / create / update / delete) with search,
  filtering, sorting and pagination; `ModelAdmin`-style config; the dynamic
  Angular SPA; session login gated by the `theia_ng.access` permission; CI that
  publishes to PyPI on a version-tag push.

[0.16.2]: https://github.com/davidsarosi92/theia_ng/releases/tag/v0.16.2
[0.16.1]: https://github.com/davidsarosi92/theia_ng/releases/tag/v0.16.1
[0.16.0]: https://github.com/davidsarosi92/theia_ng/releases/tag/v0.16.0
[0.15.0]: https://github.com/davidsarosi92/theia_ng/releases/tag/v0.15.0
[0.14.0]: https://github.com/davidsarosi92/theia_ng/releases/tag/v0.14.0
[0.13.1]: https://github.com/davidsarosi92/theia_ng/releases/tag/v0.13.1
[0.13.0]: https://github.com/davidsarosi92/theia_ng/releases/tag/v0.13.0
[0.12.1]: https://github.com/davidsarosi92/theia_ng/releases/tag/v0.12.1
[0.12.0]: https://github.com/davidsarosi92/theia_ng/releases/tag/v0.12.0
[0.11.6]: https://github.com/davidsarosi92/theia_ng/releases/tag/v0.11.6
[0.11.5]: https://github.com/davidsarosi92/theia_ng/releases/tag/v0.11.5
[0.11.4]: https://github.com/davidsarosi92/theia_ng/releases/tag/v0.11.4
[0.11.3]: https://github.com/davidsarosi92/theia_ng/releases/tag/v0.11.3
[0.11.2]: https://github.com/davidsarosi92/theia_ng/releases/tag/v0.11.2
[0.11.1]: https://github.com/davidsarosi92/theia_ng/releases/tag/v0.11.1
[0.11.0]: https://github.com/davidsarosi92/theia_ng/releases/tag/v0.11.0
[0.10.2]: https://github.com/davidsarosi92/theia_ng/releases/tag/v0.10.2
[0.10.1]: https://github.com/davidsarosi92/theia_ng/releases/tag/v0.10.1
[0.10.0]: https://github.com/davidsarosi92/theia_ng/releases/tag/v0.10.0
[0.9.0]: https://github.com/davidsarosi92/theia_ng/releases/tag/v0.9.0
[0.8.0]: https://github.com/davidsarosi92/theia_ng/releases/tag/v0.8.0
[0.7.3]: https://github.com/davidsarosi92/theia_ng/releases/tag/v0.7.3
[0.7.2]: https://github.com/davidsarosi92/theia_ng/releases/tag/v0.7.2
[0.7.1]: https://github.com/davidsarosi92/theia_ng/releases/tag/v0.7.1
[0.7.0]: https://github.com/davidsarosi92/theia_ng/releases/tag/v0.7.0
[0.6.1]: https://github.com/davidsarosi92/theia_ng/releases/tag/v0.6.1
[0.6.0]: https://github.com/davidsarosi92/theia_ng/releases/tag/v0.6.0
[0.5.0]: https://github.com/davidsarosi92/theia_ng/releases/tag/v0.5.0
[0.4.1]: https://github.com/davidsarosi92/theia_ng/releases/tag/v0.4.1
[0.4.0]: https://github.com/davidsarosi92/theia_ng/releases/tag/v0.4.0
[0.3.0]: https://github.com/davidsarosi92/theia_ng/releases/tag/v0.3.0
[0.2.0]: https://github.com/davidsarosi92/theia_ng/releases/tag/v0.2.0
[0.1.2]: https://github.com/davidsarosi92/theia_ng/releases/tag/v0.1.2
[0.1.1]: https://github.com/davidsarosi92/theia_ng/releases/tag/v0.1.1
[0.1.0]: https://github.com/davidsarosi92/theia_ng/releases/tag/v0.1.0
