# Theia NG

> A dynamic Angular admin for Django, generated from your models.

**Theia NG** brings a django-admin-style experience to a modern Angular SPA. You
register your models the way you already know — and Theia NG serves a full
CRUD admin, introspected from your ORM at runtime. No build step on your side,
no Node toolchain required.

> ℹ️ The brand is **Theia NG** (named after Theia, the Titaness of sight) — not
> to be confused with the Eclipse Theia IDE.

## Design principles

- **ORM is the source of truth.** Theia NG mirrors your Django models, not your
  API. Like `django.contrib.admin`, it ships its own auto-CRUD API so it works
  with *any* Django project — DRF not required.
- **No dependency on `django.contrib.admin`.** It builds on
  `django.contrib.auth` (permissions) and uses django admin only as a design
  reference. Its `ModelAdmin`-style registry is its own.
- **Dynamic, not generated.** Models are introspected at runtime and served as
  an intermediate representation (IR) the Angular bundle consumes. Model changes
  show up instantly — there is no client-side build.
- **DRF / OpenAPI are optional delegation targets.** If present, Theia NG can
  defer to your existing serializers/endpoints; if absent, it falls back to its
  generic auto-CRUD.
- **One prefix, runtime-configured bundle.** The SPA and its API mount under a
  single configurable prefix; the Angular bundle is prefix-independent and reads
  its config at runtime.

## Status

🟢 Working v1. Implemented and tested:

- ORM-based registry + `ModelAdmin`-style configuration (autodiscovers `theia.py`)
- Dynamic IR introspection (registry + per-model schema), cached per deploy
- Generic auto-CRUD: list (search/filter/order/paginate), create/update/delete,
  custom actions — guarded by per-model permission hooks
- Access gate via the `theia_ng.access` permission (created on migrate)
- Optional DRF delegation + OpenAPI enrichment (lazy; core never imports DRF)
- Angular 22 SPA (zoneless), served prefix-independently under one mount point

Tests: Python suite (Django 4.2 / 5.2) + frontend unit tests (Vitest).

## Supported versions

- Python 3.11 / 3.12 / 3.13
- Django 4.2 LTS (best-effort, transitional) and 5.2 LTS
- DRF 3.14+ (optional)

## Repository layout

```
theia_ng/      The Python package (the import name).
frontend/      Angular source. Built into theia_ng/static/theia_ng/ for the wheel.
tests/         A minimal Django test project + suite.
```

## License

MIT
