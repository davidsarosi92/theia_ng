# Theia NG — roadmap & working notes

Post-`/clear` start-here doc. Current released version: see `pyproject.toml`
(latest at time of writing: **0.27.2**). Repo: `~/Projects/theia-ng`
(default branch **main**, SSH remote `davidsarosi92/theia_ng`). The frontend is an
Angular **22 zoneless** SPA in `frontend/` (signals drive change detection — any
non-signal DOM binding that isn't event-driven must be made reactive via a signal;
this bit the bulk Apply button, fixed in 0.12.1).

Host project: `~/Projects/ibar-api` (Django), installs theia from PyPI
(`requirements.txt` pin, currently `theia-ng==0.27.2`) and mounts it at `/theia/`.
ibar settings: `core/settings.py` → `THEIA_NG = {... "LIST_PROVIDER":
"fastberry.list_provider.ListProvider", "SCHEMA_TTL": 300, "CACHE_VERSION":
os.getenv("THEIA_CACHE_VERSION","1") ...}`. Note that since 0.14.0 a superuser can
override `SITE_TITLE` / `LOGO_URL` / `SCHEMA_TTL` / `CACHE_VERSION` from the
Settings page (`SiteConfig` singleton, layered over `settings.py`).

---

## A. Shipped since this doc was started (0.13.0 → 0.27.2)

The original A1–A5 user-requested tasks are **all released** — nothing left there:

- **A1 i18n + locale/TZ** → 0.13.0 (runtime dictionary, 9 languages: en, hu, de,
  fr, zh, ko, ru, es, tr; `Intl`-based dates in the user's locale/timezone).
  Chrome that was still hardcoded English was swept up in 0.17.0 and 0.18.0.
- **A2 brand logo** → 0.13.0 (`THEIA_NG['LOGO_URL']`, fixed-height slot,
  `object-fit: contain`; static paths resolved in 0.14.0).
- **A3 dark/light/auto theme** → 0.13.0, dark-mode surface polish in 0.13.1.
- **A4 bulk-delete log count** → 0.13.0 (actions record an authoritative `count`).
- **A5 reorderable nav + favorites** → 0.13.0 (CDK drag-drop, handle-only grab,
  two levels: app groups + models within an app), "Reset order" in 0.13.1.

Also landed since, beyond the original list: per-user settings model + Settings
page (0.13.0/0.14.0, migrations `0006`–`0008`), admin overrides of the deploy
config + manual schema-cache flush (0.14.0), detail/object actions (0.15.0),
skeleton loaders (0.16.x), raw_id View/Edit shortcuts (0.16.2), `.distinct()`
for to-many search (0.17.0), compact/eager hierarchy + `@compact_tree`
(0.18.0–0.20.0), per-user button display preference + SVG icon set
(0.21.0–0.24.0), `ModelAdmin.description` (0.26.0), self-service password change
and the `password` widget (0.27.0), action error surfacing (0.27.1/0.27.2).

---

## B. Missing Django-admin features (backlog, tiered)

**Already in theia:** list_display/filter/search/ordering(+pk), list_per_page,
list_select_related(+auto)/prefetch, readonly_fields, exclude, fields,
**fieldsets**, **list_editable**, **inlines** (`TabularInline`/`StackedInline`,
responsive), raw_id_fields, relation pickers (autocomplete-style fk/m2m),
dependent options (relation_filters), display_field, bulk actions + checkboxes +
delete_selected + select-all-matching, **detail (per-object) actions**,
permissions, date filters (relative presets), hierarchy tree + `@compact_tree`,
menu views, favorites, audit log, **i18n (9 languages) + locale/TZ dates**,
**themes**, **per-user settings**, DRF/OpenAPI delegation, admin.py discovery,
pagination/sort/loaders, column-scoped list serialization, fast list provider
(fastberry), IR cache.

**Tier 1 — all cleared.** Inlines, i18n, fieldsets and list_editable all shipped
in 0.13.0. The next-biggest gaps are now the Tier 2 items below.

**Tier 2 (medium)**
- **`date_hierarchy` drill-down** — the only remaining piece of the old "Dates"
  item (locale/TZ-aware display shipped in 0.13.0). Discovery currently *drops*
  `date_hierarchy` (see `theia_ng/discovery.py`).
- **A real calendar / time picker widget** for date & datetime fields.
- **prepopulated_fields** (e.g. slug from title).
- **save_as** ("save as new"), **save_on_top**.
- **Per-object history** page — theia has a *global* audit log (`LogEntry`), no
  per-record view. The data is there; it needs a filtered endpoint + a tab/link
  on the detail page.
- **"Add related" (+)** — create a new related object from a relation picker.
- **list_display_links** — which column links (the whole row is clickable now).

**Tier 3 (minor / rare)**
- `filter_horizontal/vertical` dual-list M2M widget (the m2m picker covers it).
- `empty_value_display`, `search_help_text`, `formfield_overrides`.
- Custom admin views / URLs (arbitrary pages in the admin).

Suggested order: per-object history and "Add related" give the most value per
effort; `date_hierarchy` + a date picker is the biggest single chunk.

---

## C. Release process (theia → PyPI)

Tag push auto-publishes to PyPI via `.github/workflows/release.yml` (OIDC trusted
publishing); the release builds the Angular bundle (Node 24). **CI (`ci.yml`) is
tests-only — no ruff.** Steps for a release:

1. Make changes; if backend, run `./.venv/bin/python -m pytest -q` (**154 tests**
   at 0.27.2); if frontend, `cd frontend && npm run build` (must say "bundle
   generation complete").
2. Bump `pyproject.toml` `version`. (Do NOT hardcode `__init__.py.__version__` — it
   reads `importlib.metadata.version("theia_ng")`, fixed in 0.11.3.)
3. Add a `CHANGELOG.md` entry + the `[x.y.z]: …/releases/tag/vx.y.z` link line.
4. If the change touches `theia_ng/models.py`, add a migration (latest is
   `0008_usersettings_button_style`).
5. Commit (use multiple `-m` flags — heredoc commit bodies broke the shell once).
   End message with `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`.
6. `git push origin main` then `git tag -a vX.Y.Z -m "..."` and
   `git push origin vX.Y.Z` → PyPI publish.

**Note:** fastberry (`~/Projects/fastberry`, default branch **master**) is
**vcs-versioned** (the tag *is* the version, no pyproject bump) and its `ci.yml`
runs ruff + ruff format + mypy + pyright(`--verifytypes` ≥95%) — run all before
tagging. Latest fastberry: 0.4.0 (ibar is pinned to it).

---

## D. Local container injection (test before release)

The ibar web container (`ibar-api-web-1`) installs theia from PyPI; site-packages
isn't bind-mounted, so inject to test. Container theia path:
`/usr/local/lib/python3.12/site-packages/theia_ng` (Python) and
`.../theia_ng/static/theia_ng/` (the served Angular bundle).

```bash
# from ~/Projects/theia-ng
cd frontend && npm run build && cd ..              # build the bundle (dist/theia_ng/browser/)
C=ibar-api-web-1; SP=/usr/local/lib/python3.12/site-packages/theia_ng
# 1) fresh frontend bundle (clean old hashed files first, then copy)
docker compose -f ~/Projects/ibar-api/docker-compose.yml exec -T web \
  sh -c "rm -f $SP/static/theia_ng/main-*.js $SP/static/theia_ng/styles-*.css $SP/static/theia_ng/index.html"
docker cp frontend/dist/theia_ng/browser/. $C:$SP/static/theia_ng/
# 2) changed backend .py (example — copy whichever files you touched)
docker cp theia_ng/api/crud_views.py        $C:$SP/api/crud_views.py
docker cp theia_ng/introspection/builder.py $C:$SP/introspection/builder.py
docker cp theia_ng/options.py               $C:$SP/options.py
# 3) restart + verify
cd ~/Projects/ibar-api && docker compose restart web && sleep 6
```
Verify in-container (force_login a superuser, hit `/theia/api/schema/<app.model>/`
and `/theia/`); check the served `index.html` references the new `main-*.js` hash.
**Browser: hard refresh (Cmd/Ctrl+Shift+R)** after a bundle swap.

If the change adds a migration, also run `docker compose exec web python
manage.py migrate theia_ng` after injecting.

The local container often reports an older `theia_ng.__version__` (pip metadata)
while running injected newer `.py` — that's expected; behavior comes from the
injected files. ibar `core/settings.py` and `goods/theia.py` ARE bind-mounted
(live on restart).

---

## E. Repo facts

- theia tests: `cd ~/Projects/theia-ng && ./.venv/bin/python -m pytest -q`
  (pytest-django; sample app in `tests/testproject/sampleapp`). 154 tests at 0.27.2.
- frontend build: `cd frontend && npm run build` (Node 24; `node_modules` present).
- ibar is **up to date** on the pins (`theia-ng==0.27.2`, `fastberry==0.4.0`).
- **ibar cleanup still pending:** the manual `list_select_related` sweep in
  `goods/theia.py` (7 occurrences) and `structure/theia.py` (4) is redundant since
  theia ≥0.11.1 — column-scoping + auto-select_related handle it. Safe to trim,
  ideally one app at a time with a look at the list queries afterwards.
