# The list provider

The list endpoint (`GET …/data/<app.model>/`) returns one row per object. By
default Theia NG builds each row by serializing a **model instance** — it walks
every field, follows each relation, and calls `__str__`/`display()` for labels.
That per-instance, per-field work is fine for normal lists but becomes the
dominant cost on large pages or deep relation trees.

A **list provider** is an optional, swappable component that serializes a whole
page **in bulk** — typically from column-projected queries (`.values()`-style)
with no model instances at all. Theia core does not depend on any provider; you
point it at one with a single setting:

```python
THEIA_NG = {"LIST_PROVIDER": "myproject.providers.MyListProvider"}
```

The dotted path must resolve to a class with one method (it is instantiated
once, at first use):

```python
def serialize_page(self, plan, source) -> list[dict]: ...
```

When `LIST_PROVIDER` is unset (or the import fails), there is no fast path and
the generic per-instance serializer is used. **Output is identical either way** —
the provider is a pure performance optimization.

## How it fits together

```
DataListView ──> resolve_adapter(model, admin)
                   │
                   ├─ serializer_class set?  -> DRFAdapter
                   ├─ eligible + provider?   -> FastRestAdapter ──> provider.serialize_page(plan, source)
                   └─ otherwise              -> GenericAdapter  (per-instance loop)
```

Theia does two things and leaves the rest to the provider:

1. **Eligibility + plan.** `theia_ng.api.fast_list.build_plan(model, admin)`
   decides whether a model's rows are fully DB-projectable and, if so, returns a
   backend-agnostic [`FieldPlan`](#the-fieldplan). It returns `None` (→ generic
   path) when anything in a row needs a live instance.
2. **Row shaping.** After the provider returns field values, theia adds the
   `pk` and `__str__` keys and applies the final JSON coercion, so every
   provider yields theia's exact list-row contract.

## Eligibility

A model uses the fast path only when **all** of these hold (otherwise it falls
back to the generic path — never an error):

- it does not delegate to a DRF `serializer_class`;
- its `ModelAdmin.display_field` names a concrete **scalar** field — so the row
  label (`__str__`) is a column, not a Python `str(instance)`;
- **every** concrete forward FK's target model is registered with a scalar
  `display_field` — so each `{"id", "label"}` label is a projectable column;
- every **displayed** M2M's target likewise has a scalar `display_field`;
- `list_display` contains no computed columns — no admin methods, no `a__b`
  relation lookups, no model properties (those need an instance).

In short: **make your labels DB-expressible** (set `display_field` across the
admins involved) and the model opts into the fast path automatically. This is
also why relation labels are taken from the target admin's `display()`
everywhere — list rows and relation pickers stay consistent.

## The `FieldPlan`

`theia_ng.api.fast_list.FieldPlan` is a plain dataclass describing what a row
should contain. A provider consumes it (duck-typed — no need to import it):

| attribute        | type                              | meaning |
|------------------|-----------------------------------|---------|
| `model`          | Django model class                | the model to read |
| `pk_name`        | `str`                             | primary key field name (also in `scalar_fields`) |
| `display_field`  | `str`                             | scalar field used for the row's `__str__` label |
| `scalar_fields`  | `list[str]`                       | scalar columns to emit verbatim |
| `fk_labels`      | `list[(attr, label_field)]`       | forward FK → `{"id", "label"}`, label from `related.<label_field>` |
| `m2m_labels`     | `list[(attr, label_field, cap)]`  | displayed M2M → capped `[{"id","label"}, …]` (`cap` may be `None`) |

## The provider contract

`serialize_page(plan, source)` returns a list of dicts **keyed by field name**:

- scalar fields: the raw value (Decimals already stringified);
- each `fk_labels` attr: `{"id": <pk>, "label": <label>}`, or `None` for a null FK;
- each `m2m_labels` attr: a list of `{"id", "label"}`; when more than `cap`
  relate, append a `{"id": None, "label": "+N more"}` marker.

`source` is the page's queryset (a sliced queryset). Do **not** add `pk` or
`__str__` — theia adds those. Keep it free of per-row queries (resolve relations
set-based) or you lose the point.

## Writing your own provider

A minimal provider over Django `.values()` (no extra dependency):

```python
class ValuesListProvider:
    def serialize_page(self, plan, source):
        cols = list(plan.scalar_fields)
        for attr, label_field in plan.fk_labels:
            cols += [f"{attr}_id", f"{attr}__{label_field}"]
        rows = list(source.values(*cols))

        out = []
        for r in rows:
            row = {k: r[k] for k in plan.scalar_fields}
            for attr, label_field in plan.fk_labels:
                fk_id = r[f"{attr}_id"]
                row[attr] = None if fk_id is None else {
                    "id": fk_id, "label": r[f"{attr}__{label_field}"],
                }
            # (m2m omitted for brevity — fetch set-based over the through table)
            out.append(row)
        return out
```

Then:

```python
THEIA_NG = {"LIST_PROVIDER": "myproject.providers.ValuesListProvider"}
```

That's the whole extension surface. The reference implementation,
`fastberry.list_provider.ListProvider`, compiles each plan to a `FastRest`
schema (cached per model) and encodes with column-projected queries + a
set-based M2M fetch — but any class with `serialize_page(plan, source)` works,
and you don't need fastberry installed unless you use it.
