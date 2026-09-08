# LLM eval — natural-language list filtering

Measures whether a given (ideally free / self-hostable) model can turn a Hungarian
sentence into a theia list state. Feeds the decision in roadmap section F7:
**how small a model is good enough?**

## What is measured

`cases.json` — 22 Hungarian sentences against the real `goods.inventorycountheader`
admin (17 expressible + 5 traps). `schema.json` is the thin schema slice a request
would actually send: only `list_filter` fields (`status`, `start`, `finish`) with
their allowed values, plus a description of what `search_fields` covers.

The traps matter more than the easy cases. The model must **refuse** rather than
improvise when the request needs something the filter DSL lacks:

| # | sentence | why it cannot be expressed |
|---|---|---|
| 18, 19 | "2025 márciusa előtt", "január és március között" | no operators/ranges in `_apply_date_filter` |
| 20, 21 | "amit Nagy Péter hozott létre", "Konyha kategóriájú" | `created_by` / `inventory_category` are neither filterable nor searchable |
| 22 | "archivált leltárak" | not a valid `status` choice |

## Verdicts

- `OK` — filters, search and ordering all match (search is matched by containment)
- `PARTIAL` — filters+search right, sort missed; or a trap routed to search instead of flagged
- `WRONG` — wrong but legal values
- `HALLUCINATED` — invented a field name or an out-of-vocabulary value
- `UNPARSABLE` — no JSON in the reply

`HALLUCINATED` is the one that disqualifies a model: it silently produces a
*plausible wrong list*, which is exactly the failure mode that must never reach a
delete confirmation.

**Bar for shipping: 0 HALLUCINATED, 0 UNPARSABLE, OK ≥ 80%.**

## Running

Provider-agnostic, stdlib only — same OpenAI-compatible contract the planned
theia adapter will use, so every backend is just a different `--base-url`.

```bash
# local (Ollama) — start it with the compose stack in ../../theia-ng-llm
cd ../../theia-ng-llm && docker compose up -d && cd -
python3 run.py --base-url http://localhost:11434/v1 --model qwen2.5:3b --json-schema

# any hosted OpenAI-compatible endpoint
python3 run.py --base-url https://.../v1 --model <name> --api-key "$KEY"

# keep the full transcript for inspection
python3 run.py ... --out results-qwen3b.json
```

`--json-schema` requests constrained JSON decoding (Ollama and vLLM support it).
Run each model **both with and without it** — the delta is itself a result: if a
model only behaves under constrained decoding, that is a hard requirement for the
adapter, not an optimization.
