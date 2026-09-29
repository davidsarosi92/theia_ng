# Theia NG — roadmap & working notes

Post-`/clear` start-here doc. Current released version: see `pyproject.toml`
(latest at time of writing: **0.30.0**). Repo: `~/Projects/theia-ng`
(default branch **main**, SSH remote `davidsarosi92/theia_ng`). The frontend is an
Angular **22 zoneless** SPA in `frontend/` (signals drive change detection — any
non-signal DOM binding that isn't event-driven must be made reactive via a signal;
this bit the bulk Apply button, fixed in 0.12.1).

Host project: `~/Projects/ibar-api` (Django), installs theia from PyPI
(`requirements.txt` pin, currently `theia-ng==0.27.2` — **behind**, see E) and
mounts it at `/theia/`.
ibar settings: `core/settings.py` → `THEIA_NG = {... "LIST_PROVIDER":
"fastberry.list_provider.ListProvider", "SCHEMA_TTL": 300, "CACHE_VERSION":
os.getenv("THEIA_CACHE_VERSION","1") ...}`. Note that since 0.14.0 a superuser can
override `SITE_TITLE` / `LOGO_URL` / `SCHEMA_TTL` / `CACHE_VERSION` from the
Settings page (`SiteConfig` singleton, layered over `settings.py`).

---

## A. Shipped since this doc was started (0.13.0 → 0.30.0)

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
and the `password` widget (0.27.0), action error surfacing (0.27.1/0.27.2),
natural-language assistant (0.28.0, section F) + ⌘K omnibox (0.29.0), personal
list columns + the `?columns=`/`?ordering=` allowlist security fix (0.30.0,
migration `0011`).

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

**Personal list columns** shipped in 0.30.0 (per-user column pick/order over a
code-defined pool; `list_display_optional`, `list_customizable`; migration
`0011`) together with the `?columns=` / `?ordering=` allowlist security fix.
Possible follow-ups: per-user form-field hiding, per-user `list_per_page`.

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

1. Make changes; if backend, run `./.venv/bin/python -m pytest -q` (**216 tests**
   at 0.30.0); if frontend, `cd frontend && npm run build` (must say "bundle
   generation complete").
2. Bump `pyproject.toml` `version`. (Do NOT hardcode `__init__.py.__version__` — it
   reads `importlib.metadata.version("theia_ng")`, fixed in 0.11.3.)
3. Add a `CHANGELOG.md` entry + the `[x.y.z]: …/releases/tag/vx.y.z` link line.
4. If the change touches `theia_ng/models.py`, add a migration (latest is
   `0011_usersettings_list_columns`).
5. Commit (use multiple `-m` flags — heredoc commit bodies broke the shell once).
   End message with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
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
`/usr/local/lib/python3.13/site-packages/theia_ng` (Python) and
`.../theia_ng/static/theia_ng/` (the served Angular bundle).

```bash
# from ~/Projects/theia-ng
cd frontend && npm run build && cd ..              # build the bundle (dist/theia_ng/browser/)
C=ibar-api-web-1; SP=/usr/local/lib/python3.13/site-packages/theia_ng
# 1) fresh frontend bundle (clean old hashed files first, then copy)
docker compose -f ~/Projects/ibar-api/docker-compose.yml exec -T web \
  sh -c "rm -f $SP/static/theia_ng/main-*.js $SP/static/theia_ng/styles-*.css $SP/static/theia_ng/index.html"
docker cp frontend/dist/theia_ng/browser/. $C:$SP/static/theia_ng/
# 2) the whole Python package (safer than single files: when the pip-installed
#    version is older, new modules/migrations it lacks come along too)
docker exec $C sh -c "rm -rf /tmp/theia_ng_backup && cp -a $SP /tmp/theia_ng_backup"
tar -C theia_ng --exclude __pycache__ --exclude ./static -cf - . | docker exec -i $C tar -C $SP -xf -
# 3) restart + verify
cd ~/Projects/ibar-api && docker compose restart web && sleep 6
```
Verify in-container (force_login a superuser, hit `/theia/api/schema/<app.model>/`
and `/theia/`); check the served `index.html` references the new `main-*.js` hash.
**Browser: hard refresh (Cmd/Ctrl+Shift+R)** after a bundle swap.

If the change adds a migration, also run `docker compose exec web python
manage.py migrate theia_ng` after injecting. If it changes the IR, flush the
schema cache (Settings → Clear schema cache): ibar pins `CACHE_VERSION` to "1",
so a stale schema otherwise survives until `SCHEMA_TTL` expires.

The local container often reports an older `theia_ng.__version__` (pip metadata)
while running injected newer `.py` — that's expected; behavior comes from the
injected files. ibar `core/settings.py` and `goods/theia.py` ARE bind-mounted
(live on restart).

---

## E. Repo facts

- theia tests: `cd ~/Projects/theia-ng && ./.venv/bin/python -m pytest -q`
  (pytest-django; sample app in `tests/testproject/sampleapp`). 216 tests at 0.30.0.
- frontend build: `cd frontend && npm run build` (Node 24; `node_modules` present).
- ibar's pin is **behind**: `theia-ng==0.27.2` (latest 0.30.0 — includes a
  security fix), `fastberry==0.4.0` is current. The local container runs injected
  0.30.0 code with migrations through `0011` applied.
- **ibar cleanup still pending:** the manual `list_select_related` sweep in
  `goods/theia.py` (7 occurrences) and `structure/theia.py` (4) is redundant since
  theia ≥0.11.1 — column-scoping + auto-select_related handle it. Safe to trim,
  ideally one app at a time with a look at the list queries afterwards.

---

## F. LLM assistant — natural-language list filtering (design, not started)

**Goal.** The user *describes* what they want instead of navigating to it:
"töröld ki az inventory-headerből a tavalyi lezártakat" → the list is filtered to
those rows and a delete button appears. Motivation: on a wide admin, describing a
target is easier than clicking your way to it.

**Core principle: the LLM builds a query, it never executes anything.** It emits a
*list state* (the same shape the filter UI produces); the user sees the matching
rows and confirms. Deletion then runs through the existing `delete_selected` with
its normal permission checks and `audit.record`. Worst case for a misread prompt
is a wrong list, never a wrong delete.

### F1. What the model must produce

Theia's list state is already fully serialized into the URL query
(`model-list.component.ts:452-469`), so the LLM's whole job is to fill in a small
JSON object — no SQL, no ORM, no new result rendering:

- `search` — free text, matched against the admin's `search_fields`
- `filters` — `AppliedFilter[]` = `{field, label, value, display}`
- `ordering` — an optional sort column

**Both `search` and `filters` matter.** `list_filter` is often tiny (for
`InventoryCountHeaderAdmin` it is just `start`, `finish`, `status`), while
`search_fields` reaches deep relations (house / company / space / registration
names). Filters carry the status+date dimension, search carries the "which
customer/place" dimension. Using only one of the two would make most real
sentences unexpressible.

**Known DSL limit.** `_apply_date_filter` (`api/crud_views.py:176-203`) supports
only a preset (`today`, `last_2_days`, `last_7_days`, `last_30_days`,
`last_year`) or one exact calendar day — there are **no operators or ranges**. So
"before 2026-01-01" or "during March 2025" cannot be expressed today. Decide
early whether to (a) cap the assistant at the current DSL, or (b) extend filters
with operators (`lt`/`gt`/`between`) — (b) is the more useful feature but it also
touches the existing filter dialog and the URL format.

### F2. Provider abstraction (must be swappable, must be optional)

Follow the pattern the repo already uses for DRF/fastberry: `theia_ng/adapters/`
+ lazy imports + graceful fallback. The pyproject rule ("Core depends ONLY on
django.contrib.auth") stays intact.

```python
THEIA_NG = {
    "LLM": {
        "PROVIDER": "openai_compatible",
        "BASE_URL": "http://localhost:11434/v1",   # Ollama / llama.cpp / vLLM / hosted
        "MODEL": "llama3.1:8b",
        "API_KEY": os.getenv("THEIA_LLM_KEY", ""),  # empty for local
        "TIMEOUT": 20,
    },
}
```

**No new Python dependency.** An OpenAI-compatible `/v1/chat/completions` call is
stdlib `urllib.request` + `json`. One HTTP contract covers Ollama, llama.cpp
server, vLLM, OpenRouter, Groq and the commercial APIs — swapping provider is a
`BASE_URL` change, not a code change. Optional extras are only ever for
convenience SDKs, never required.

**Never run the model in-process.** Weights are GB-scale (8B Q4 ≈ 5 GB, 3B ≈ 2 GB),
gunicorn forks workers, and `torch`/`llama-cpp-python` are exactly the kind of
dependency this package refuses to carry. The model is always a separate process
behind HTTP — for ibar, one more compose service alongside redis/celery.

### F3. Making a small/free model work

A local 3–8B model can do this **only** if the task is kept narrow:

*Measured, not assumed — see `docs/llm-eval/RESULTS.md`.*

1. **Thin schema slice.** Send only the one model's filterable fields + choices,
   never the whole IR. Deep chains (`space__house__company__registration__
   integration`) invite hallucinated field names.
2. **Per-field value enums, not just a JSON schema.** Measurement 1 showed a plain
   JSON schema does *not* stop hallucination — it constrains the shape, and
   `{"type":"string"}` still accepts `field: "space"`. Encoding the vocabulary as
   `oneOf` variants (`field: {const}` + `value: {enum}`) made invalid output
   structurally undecodable and drove HALLUCINATED to 0. This belongs in the
   adapter: it is the only hard guarantee available.
3. **Ship the localized labels in the schema slice.** Sending
   `"cancelled" = megszakított / törölt` instead of bare `cancelled` was worth
   ~9 points on Hungarian input, and costs nothing — Django choice labels and
   `verbose_name` are already translated in a localized project. Quote the value
   and mark the gloss with `=`; the natural `cancelled (megszakított)` format made
   models emit the whole string as the value.
4. **No value guessing.** The model must not invent PKs; it emits names and
   theia resolves them (or routes them into `search`).
5. **Reward staying silent.** The residual failure of small models is precision,
   not vocabulary: they attach a spurious filter to a pure name search and fill in
   an answer for unsupported requests rather than flagging them. The contract needs
   an explicit, encouraged "empty filters + unsupported[]" escape hatch.

### F4. Not breaking anything

- **`THEIA_NG["LLM"]` absent ⇒ the feature does not exist.** The flag rides the
  existing SPA config injection (`views.py:62`, next to `logoUrl`); with it off
  there is no route, no endpoint, no UI. Zero change for existing installs.
- **No migration in v1** — the conversation lives in frontend memory only, so
  `models.py` is untouched (`0008` stays the last migration).
- **The endpoint is read-only** — NL in, validated list state out. It never writes.
- **`has_access` gating on the schema slice too**, or it leaks field names of
  models the user may not see.
- **Hard timeout + fallback** to the normal filter dialog; the manual path must
  always stay available and must never become AI-only.
- **Worker blocking:** a multi-second sync call holds a gunicorn worker. Low QPS
  makes this survivable, but the timeout has to be strict.

### F5. Privacy

The schema field names and the user's typed text (which may contain customer
names) go to whatever endpoint is configured. For a host like ibar that is a real
constraint and an argument for local Ollama or a deliberately chosen provider in
production — another reason the provider must be swappable.

### F6. UI sketch

Two panes, not three — the "feedback" *is* a chat turn, and splitting it from the
conversation makes the user look in two places at the moment that matters most
(checking the interpretation before a delete):

- left (~380px): the conversation; each answer renders an interpretation card
  ("Inventory header · status = uploaded · start ≥ … → 47 rows") whose chips are
  editable `AppliedFilter`s, with the delete button on the card
- right: the existing `ModelListComponent`, reused, not a new table

**Implemented as a side panel on the list page** rather than a separate route:
the list behind it *is* the result surface, so it stays visible while the request
is refined. The entry point appears only when `assistEnabled` reaches the SPA.
A trash control in the panel header clears the session's conversation — screen
only; the audit trail of what was asked is untouched, and the confirm dialog says
so. The prompt bubble appears the moment you ask, not when the answer lands (the
model can take 5-20 s).

Still open: a Cmd+K omnibox from anywhere, which is what would deliver "just type
it" outside the list page.

**Every prompt is audited** (`LogEntry.ASSIST`, migration `0010`) with the user,
the sentence, the interpreted intent, the filters and the match count — including
prompts that were downgraded or refused, or "what did they try to do" would have
a hole in it. The write that follows a confirmation is audited separately by the
endpoint performing it, so instruction and effect stay distinct events.

### F6b. Editable LLM hints — measured, and rejected

An admin-editable table of prompt hints was proposed and measured against a
**held-out** set of 22 new sentences (`docs/llm-eval/cases-holdout.json`). Both
variants improved the set they were written against and made the model **worse**
on fresh input: no hints **82%**, descriptive hints 73%, keyword-list hints 59%.
Run-to-run variance is zero (`temperature: 0`), so the gap is reproducible, not
noise.

**Built anyway, deliberately** (`AssistHint` + `AssistExample`, migration `0009`).
The measurement covers one model family at one size; whether a stronger model
benefits from nuanced instructions is not something a 7B result can settle. So
the tables exist and ship **empty**, with the finding written into the admin
page's own description, and a hard `MAX_HINT_CHARS` budget so a deployment cannot
grow the prompt without bound.

Three kinds in one table — model description, per-field explanation, dictionary
term — plus `AssistExample` for worked examples. Examples are `in_prompt=False`
by default: an example is useful as a **regression case** even when it is not
few-shot material, and that is the point. Any hint edit can be replayed against
them, which is the only way a well-meant hint that quietly costs 20 points gets
caught instead of shipped.

Both admins set `assist = False` — the assistant must not be steerable through
itself.

### F6c. Delete and create (implemented)

The assistant classifies a request as `filter`, `delete` or `create` and returns
a **proposal**; an irreversible one goes to a modal showing the real queryset
(exact count + sample rows, built with the same `apply_list_filters` the delete
will use) and an explicit warning that it cannot be undone.

**The LLM still executes nothing.** A confirmed proposal is carried out by the
endpoints that already exist — `delete_selected` with select-all-matching, and
`POST data/` — so permission checks, `full_clean()` and the audit entry apply
exactly as they would without the assistant. No privileged path was added.

Four downgrades turn an unsafe proposal back into a harmless filter: a delete
with no filter (it would match the whole table — that has to be deliberate, not a
misparse), no delete permission, zero matching rows, and a create with no usable
values. Create excludes relations: setting an FK means guessing an identity, and
an incomplete create beats one silently attached to the wrong parent.

### F7. Open question driving everything

**How small a model suffices?** Harness and full write-up in `docs/llm-eval/`
(`run.py` is stdlib-only and provider-agnostic — every backend is a `--base-url`).

**Measured 2026-09-08 (local Ollama, M2 Pro). There is a capability cliff between
3B and 7B, and the answer is 7B.**

| model | OK | HALLUC | median | unsupported flagged |
|---|---|---|---|---|
| **qwen2.5:7b** | **77%** | 0 | **1.6 s** | **5/5** |
| qwen3:8b | 77% | 0 | 11.2 s (max 40.8) | 3/5 |
| llama3.1:8b | 45% | 0 | 1.3 s | 2/5 |
| qwen2.5:3b | 36% | 0 | 0.7 s | 1/5 |
| llama3.2:3b | unusable — hung past 120 s, invented field names | | | |

**Pick `qwen2.5:7b`. Two traps to avoid when choosing a model:**
- **Do not shop by parameter count.** `llama3.1:8b` is *bigger* than the 7B and
  scored 45% against its 77%; the llama family failed at 3B too. Family and
  training dominate size on this task.
- **Do not use a reasoning model.** `qwen3:8b` made the fewest hard errors of all
  (91% OK+PARTIAL) but costs **11.2 s median, 40.8 s worst case** — it thinks
  before answering. Unusable for a box the user types into.

The decisive column is the last one. The 3B tier does not know **when to refuse**:
it invents a filter state for requests the DSL cannot express. That disqualifies
it from a delete flow regardless of its other numbers. The 7B flagged all five.

**Latency is not the constraint** (1.6 s, ~430-token prompt) — on an M2 Pro. A
server without a GPU must be measured separately before committing.

**77% is under the 80% bar and is not rounded up.** All four residual failures are
the same `start` vs `finish` confusion; better field labels would probably fix
them, but with only 22 cases, tuning against those four would be overfitting.

**Before building, two things:** (1) confirm on a strong hosted model that the
ceiling is ≥90% — otherwise the design, not the model, is the problem; (2) expand
the case set well beyond 22 and re-measure the 7B on it.

**Also learned, and it belongs in the adapter:** Ollama's grammar honours `enum`
but not a nested `anyOf`/`pattern`, so exact `YYYY-MM-DD` values cannot be
constrained structurally there. **Server-side validation + retry is therefore
mandatory, not an optimization** — no runtime's grammar can be assumed to cover
the whole value space.
