# Changelog

All notable changes to **Theia NG** are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and the project follows
[Semantic Versioning](https://semver.org/).

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
