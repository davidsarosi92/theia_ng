# Measurement 1 — local models (2026-09-08)

Hardware: Apple M2 Pro, 32 GB. Runtime: Ollama 0.x via Homebrew, models Q4.
22 Hungarian cases against the real `goods.inventorycountheader` admin.

## Numbers

| run | model | schema | strict values | OK | PARTIAL | WRONG | HALLUC | median |
|---|---|---|---|---|---|---|---|---|
| 1 | qwen2.5:1.5b | EN | no | 3 (14%) | 4 | 15 | 0 | 0.6 s |
| 2 | qwen2.5:3b | EN | no | 7 (32%) | 2 | 11 | **2** | 0.7 s |
| 3 | qwen2.5:3b | HU | **yes** | 9 (41%) | 0 | 13 | 0 | 0.6 s |
| 4 | qwen2.5:1.5b | HU | **yes** | 9 (41%) | 2 | 11 | 0 | 0.4 s |
| — | llama3.2:3b | both | both | — | — | — | ≥3 | timed out |

`llama3.2:3b` never completed a run: it repeatedly hung past a 120 s timeout, and
before hanging it invented field names (`space`, `space__name`) and copied label
text into values. Excluded as unusable, not scored.

**Nothing in this first round cleared the bar.** Best small-model result: 41%.
See "Round 2" below — a 7B model with a corrected instrument reaches 77%.

## What the runs actually taught us

**1. Constrained JSON decoding does NOT prevent hallucination by itself.** Run 2
had a JSON schema and still emitted `field: "space"` — because the schema
constrained the *shape*, not the vocabulary. `{"type":"string"}` accepts anything.

**2. Per-field value enums (`oneOf` with `field: {const}` + `value: {enum}`) do.**
Runs 3–4 make an invalid field/value combination structurally undecodable, and
HALLUCINATED went to 0. **This belongs in the adapter, not in the prompt** — it is
the only mechanism here that gives a hard guarantee rather than a tendency.

**3. Localized labels are worth ~9 points.** Sending the choices as
`"cancelled" = megszakított / törölt` instead of bare `cancelled` fixed the whole
Hungarian vocabulary class (cases 1,2,3,4,6,7,8,17). This is free in production:
Django choice labels and `verbose_name` are already translated in a Hungarian
project, so the schema slice should carry them.

**4. Label format matters, and the obvious format is a trap.** Writing
`cancelled (megszakított)` made the model emit the *whole string* as the value.
Quoting the value and marking the gloss with `=` fixed it. Worth remembering when
writing the real prompt builder.

**5. The remaining failure is judgment, not vocabulary.** After runs 3–4 the
models know the field names and values but not *when to stay silent*: they attach
a spurious `status` filter to a pure name search ("a Kossuth utcai raktár
leltárai" → `status=pending`) and they fill in a filter for the unsupported cases
instead of flagging them. Precision, not recall, is what a 1.5–3B model lacks —
and precision is exactly what a delete flow needs.

Note the tension in the traps: run 2 (loose) flagged all 5 correctly, run 3
(strict) flagged 1. Tightening the value space pushed the model toward always
producing *something*. A production adapter probably needs both — strict values
**and** an explicit "return an empty filter list" escape hatch that is rewarded.

## Not yet answered: the ceiling

There is no strong-model baseline in this table, so it does not yet distinguish
"1.5–3B models are too weak" from "the prompt or the test set is wrong". A
`qwen2.5:7b` run was attempted and aborted — the 4.7 GB pull did not fit in the
free disk (and filled it; the partial blob was cleaned up afterwards).

**This is the next measurement**, and it is the one that decides roadmap F7. Run
the same harness against one strong hosted model (any OpenAI-compatible endpoint)
and one 7–8B local model:

- if a strong model scores ≥ 90%, the task is well-posed and the answer is "small
  local models are not enough" → hosted endpoint, or a GPU box, or scope the
  feature down
- if a strong model also scores poorly, the harness/prompt is at fault and the
  design needs rethinking before any model choice matters

## Reproducing

```bash
cd theia-ng-llm && docker compose up -d && cd -   # Ollama + the model
cd docs/llm-eval
python3 run.py --base-url http://localhost:11434/v1 --model qwen2.5:3b \
    --json-schema --strict-values --schema schema-hu.json --out results-x.json
```

Needs ~2 GB free disk per 3B model (the 7B is ~4.7 GB). `run.py` is stdlib-only
and provider-agnostic — any backend is just a different `--base-url`.


---

# Round 2 — qwen2.5:7b, and two instrument bugs (same day)

## The instrument was wrong twice

Round 1's numbers were depressed by two bugs in the harness, both found by
running a stronger model — its failures were legible where a 3B's noise was not.

**Bug A — the strict-value constraint did not cover date fields.** `--strict-values`
enumerated values only for `choice` fields; date fields kept `{"type": "string"}`
so an exact `YYYY-MM-DD` would stay possible. That hole let `finish: "ma"` (the
Hungarian *label*) through as a hallucination.

**Bug B — spurious ordering.** The prompt described sorting without saying *when*
not to sort, so the model attached `ordering: "start"` to requests that never
mentioned order. Worth 4 PARTIALs on the 7B alone. Fixed by making the null case
explicit.

**A finding from fixing Bug A:** Ollama's grammar honours `enum`, but **not** a
nested `anyOf`/`pattern` — the first fix (`anyOf: [{enum}, {pattern: YYYY-MM-DD}]`)
changed nothing and the hallucination persisted. Only a flat `enum` closed it.
So exact calendar dates cannot be constrained structurally on this runtime.

> **Design consequence:** structural constraints cannot cover the whole value
> space on every runtime. Server-side validation + retry is **mandatory** in the
> adapter regardless of what the grammar promises — it is not an optimization.

## Numbers (corrected instrument, HU schema, strict values)

| model | OK | +PARTIAL | WRONG | HALLUC | median | traps (5) |
|---|---|---|---|---|---|---|
| qwen2.5:7b | **17 (77%)** | 82% | 4 | **0** | 1.6 s | **5/5** |
| qwen2.5:3b | 8 (36%) | 36% | 14 | 0 | 0.7 s | 1/5 |

Progression on the 7B as the instrument was fixed: 55% → 73% → **77%**.

## Verdict

**The task is well-posed** — a 7B model gets 77% with zero hallucinations and
zero unparsable replies, at 1.6 s. Round 1's pessimism was partly my instrument.

**There is a real capability cliff between 3B and 7B**, and it is not vocabulary:
both had the same labels and the same constrained decoding. It is judgment. The
clearest signal is the traps — the 7B flagged **5 of 5** unsupported requests,
the 3B flagged **1 of 5**. A model that invents an answer for a request it cannot
express is disqualified from a delete flow no matter how good its other numbers.

**77% is just under the 80% bar and should not be rounded up.** The 4 remaining
failures (cases 8, 9, 10, 14) are all the same confusion — `start` vs `finish`
("tavaly óta *indult*", "múlt heti", "*mai* leltárai"). Better field labels would
likely fix them, but that must be measured on *new* sentences: at 22 cases,
tuning against these four is overfitting.

## What this means for F7

- **Self-hosting is viable**, but at 7B, not 3B: ~5 GB, ~1.6 s per request on an
  M2 Pro. On a server without a GPU expect meaningfully slower — measure there.
- **The 3B tier is out.** Not a tuning problem; it does not know when to refuse.
- **Before building:** confirm on a strong hosted model that the ceiling is ≥90%,
  and expand the case set (22 is too few, and 4 of the failures now cluster on one
  distinction). Then re-measure the 7B on the expanded set.


---

# Round 3 — the 8B question: size is not the axis

| model | params | OK | +PARTIAL | WRONG | HALLUC | median | traps |
|---|---|---|---|---|---|---|---|
| **qwen2.5:7b** | 7B | **77%** | 82% | 4 | 0 | **1.6 s** | 5/5 |
| qwen3:8b | 8B | **77%** | **91%** | **2** | 0 | **11.2 s** (max 40.8) | 3/5 +2 partial |
| llama3.1:8b | 8B | 45% | 50% | 11 | 0 | 1.3 s | 2/5 |
| qwen2.5:3b | 3B | 36% | 36% | 14 | 0 | 0.7 s | 1/5 |

**Going bigger did not help; changing family did.** `llama3.1:8b` is larger than
`qwen2.5:7b` and scored 45% against its 77% — and the llama family failed at 3B
too (`llama3.2:3b` was unusable). Model family and training matter far more than
parameter count on this task. Do not shop by size.

**`qwen3:8b` is the quality ceiling seen so far but is disqualified on latency.**
It made the fewest hard errors of any model (2 WRONG, 91% OK+PARTIAL) — and cost
**11.2 s median, 40.8 s worst case**, because it is a reasoning model that spends
tokens thinking before answering. For a box the user types into, that is not
usable. Reasoning models buy accuracy with exactly the resource this feature
cannot spend.

**`qwen2.5:7b` remains the pick:** same 77% OK at 1.6 s, and the best trap record
(5/5 refusals).

## Standing conclusion

A free, self-hostable, non-reasoning ~7B model reaches **77% with zero
hallucinations at 1.6 s** on an M2 Pro. That is close to, but not at, the 80% bar,
and it is measured on only 22 cases.

The two open items from Round 2 are unchanged and still gate the build:
1. no strong-hosted-model ceiling yet (is ≥90% even reachable?);
2. 22 cases is too few, and four of the 7B's failures cluster on one distinction
   (`start` vs `finish`) — expand the set before tuning anything.


---

# Round 4 — do editable "hints" help? No. (same day)

The proposal: an admin-editable table of hints (model description, per-field
explanations, domain vocabulary) folded into the prompt when the LLM feature is
on. The motivation was real — ibar's `InventoryCountHeader` has no
`verbose_name`, so the slice went out as `start | start`, losing the label
benefit Round 1 measured.

**To avoid tuning against the answers, a held-out set of 22 new Hungarian
sentences (`cases-holdout.json`) was written first**, and every variant measured
on both sets. This turned out to be the whole point.

| hint variant | prompt cost | original 22 | **held-out 22** |
|---|---|---|---|
| **none** | — | 77% | **82%** ← best |
| descriptive (`start` = "a leltározás megkezdésének időpontja") | 202 chars | 82% | 73% |
| keyword lists ("ide tartozik minden 'indított', 'elkezdett'…") | 500 chars | **86%** | **59%** |

**Both hint variants improved the set they could be checked against and made the
model worse on fresh sentences.** That is the signature of overfitting, and it is
exactly what the held-out set was built to catch.

**Run-to-run variance is zero.** Three repeats of the two held-out cells returned
identical scores (18/22 and 16/22 every time) — `temperature: 0` makes this
deterministic. So the 82% → 73% gap is *not* sampling noise. The remaining
uncertainty is the sample of 22 *sentences*, not the model: more sentences would
narrow it, more runs would not.

## Why hints hurt

The keyword variant is diagnosable. Told that "indított / elkezdett" belong to
`start`, the model became a keyword matcher:

```
> amit Szabó Anna kezdett el   → start=today       (a PERSON, not a date)
> tegnap óta megkezdett munkák → start=today       (wanted last_2_days)
> a jóváhagyásra váró leltárak → invented a filter instead of flagging
```

The descriptive variant carried no keyword lists and was written generically, yet
still lost two cases. Its failures are all *over-production* — a spurious extra
filter attached to an otherwise correct answer:

```
> a ma véglegesített ívek   → finish=today + a spurious status filter
> a folyamatban lévők…      → two spurious date filters
```

The working hypothesis: **added prose dilutes the hard rules** ("never invent",
"put unexpressible requests into unsupported"), and the model drifts toward
answering rather than refusing. Note the trap case regressed in both variants.

## Revised recommendation

**Do not ship a free-text hint table.** There is no evidence it helps and
reproducible evidence it hurts, on a 7B model at least.

**A label/synonym override table is a different thing and is supported.** Round 1
measured localized labels as worth ~9 points, and ibar's missing `verbose_name`
is a *label* gap, not a hint gap. An override table gives that benefit without
adding prose to the prompt.

**Few-shot example pairs remain untested** — the one hypothesis with a strong
prior that has not been measured here. Measure on the held-out set before
building anything.

**If free-text hints are ever added anyway,** they must ship with the example-pair
regression set, not as a later nicety: a well-meaning admin will write exactly the
keyword list that cost 23 points, and without measurement nobody will notice.
