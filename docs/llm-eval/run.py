#!/usr/bin/env python3
"""Measure how well a given LLM turns Hungarian sentences into a theia list state.

Provider-agnostic: talks OpenAI-compatible /v1/chat/completions over stdlib HTTP,
exactly like the planned theia adapter — so Ollama, llama.cpp, vLLM, OpenRouter,
Groq and the commercial APIs are all just a different --base-url/--model.

  python3 run.py --base-url http://localhost:11434/v1 --model llama3.2:3b
  python3 run.py --base-url ... --model ... --api-key $KEY --json-schema
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request

HERE = pathlib.Path(__file__).parent
SCHEMA = json.loads((HERE / "schema.json").read_text())  # replaced by --schema
CASES = json.loads((HERE / "cases.json").read_text())

# The JSON contract the model must fill in. Kept deliberately small: the whole
# point is that this is a form-filling task, not a query-writing task.
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "search": {"type": "string"},
        "filters": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"field": {"type": "string", "enum": []}, "value": {"type": "string"}},
                "required": ["field", "value"],
            },
        },
        "ordering": {"type": ["string", "null"]},
        "unsupported": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["search", "filters", "ordering", "unsupported"],
}


def build_prompt(schema: dict) -> str:
    model_hint = f'\n{schema["model_hint"]}' if schema.get("model_hint") else ""
    search_hint = f' {schema["search_hint"]}' if schema.get("search_hint") else ""
    fields = []
    for f in schema["filter_fields"]:
        label = f.get("label", f["name"])
        hint = f' — {f["hint"]}' if f.get("hint") else ""
        if f["type"] == "choice":
            cl = f.get("choice_labels") or {}
            vals = "; ".join(f'"{c}"' + (f' = {cl[c]}' if c in cl else "") for c in f["choices"])
            fields.append(f'- {f["name"]} — "{label}"{hint} — use exactly one of: {vals}')
        else:
            pl = f.get("preset_labels") or {}
            vals = "; ".join(f'"{c}"' + (f' = {pl[c]}' if c in pl else "") for c in f["presets"])
            fields.append(
                f'- {f["name"]} — "{label}"{hint} — use exactly one of: {vals}; '
                f'or an exact day as "YYYY-MM-DD"'
            )
    return f"""You translate a user's request into a filter state for an admin list view.

MODEL: {schema["verbose_name"]} — {schema["description"]}{model_hint}

You may ONLY filter on these fields, using ONLY the listed values:
{chr(10).join(fields)}

FREE-TEXT SEARCH: {schema["search_description"]}{search_hint}
Put names of places, companies, people or external keys into "search", NOT into a filter.

SORTING: only if the user explicitly asks for an order, sort by one of
{", ".join(schema["ordering_fields"])}; prefix with "-" for descending.
If the user says nothing about ordering, "ordering" MUST be null.

Reply with JSON only:
{{"search": "<text or empty string>",
  "filters": [{{"field": "<field name>", "value": "<allowed value>"}}],
  "ordering": "<field, -field, or null>",
  "unsupported": ["<anything requested that you could NOT express>"]}}

HARD RULES:
- Copy values EXACTLY as quoted above. The text after "=" is only a translation hint,
  never part of the value. A value belongs only to its own field.
- There are NO comparison operators and NO date ranges. "before X", "between X and Y",
  or a specific month cannot be expressed — put such a request into "unsupported".
- If a requested value is not in the allowed list, put it into "unsupported".
- The user's request may be about deleting; you only build the filter, never delete.
- Output JSON and nothing else."""


def call(base_url, model, api_key, prompt, user_text, timeout, use_json_schema):
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_text},
        ],
        "temperature": 0,
        "stream": False,
    }
    if use_json_schema:
        body["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": "list_state", "strict": True, "schema": OUTPUT_SCHEMA},
        }
    data = json.dumps(body).encode()
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions", data=data, headers=headers
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        payload = json.loads(r.read())
    return payload["choices"][0]["message"]["content"], time.time() - t0


def parse(raw: str):
    """Models wrap JSON in prose or fences often enough that we must be tolerant."""
    if raw is None:
        return None
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.M).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", raw, re.S)
        if not m:
            return None
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            return None


VALID_FIELDS = {f["name"] for f in SCHEMA["filter_fields"]}
VALID_VALUES = {
    f["name"]: set(f.get("choices") or f.get("presets") or []) for f in SCHEMA["filter_fields"]
}


def norm_filters(fs):
    out = set()
    for f in fs or []:
        if isinstance(f, dict) and "field" in f and "value" in f:
            out.add((str(f["field"]), str(f["value"])))
    return out


def hallucinated(got):
    """Invented field names, or values outside the allowed set — the failure that
    actually matters, because it produces a wrong list rather than no list."""
    bad = []
    for field, value in norm_filters(got.get("filters")):
        if field not in VALID_FIELDS:
            bad.append(f"field:{field}")
        elif VALID_VALUES[field] and value not in VALID_VALUES[field]:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                bad.append(f"value:{field}={value}")
    return bad


def score(case, got):
    """-> (verdict, detail). Verdicts: OK, PARTIAL, WRONG, HALLUCINATED, UNPARSABLE"""
    if got is None:
        return "UNPARSABLE", "no JSON in reply"

    bad = hallucinated(got)
    if bad:
        return "HALLUCINATED", ", ".join(bad)

    if not case["expressible"]:
        # Success = admitting it, not silently producing something plausible.
        if got.get("unsupported"):
            return "OK", "flagged unsupported"
        if not norm_filters(got.get("filters")) and got.get("search"):
            return "PARTIAL", "routed to search instead of flagging"
        return "WRONG", "produced a filter state instead of flagging unsupported"

    exp = case["expect"]
    want_f, have_f = norm_filters(exp["filters"]), norm_filters(got.get("filters"))
    want_s = (exp["search"] or "").lower().strip()
    have_s = str(got.get("search") or "").lower().strip()
    # Search text is fuzzy by nature: accept containment either way.
    search_ok = want_s == have_s or (bool(want_s) and (want_s in have_s or have_s in want_s))
    want_o, have_o = exp["ordering"], got.get("ordering")
    order_ok = (want_o or None) == (have_o or None)

    if want_f == have_f and search_ok and order_ok:
        return "OK", ""
    parts = []
    if want_f != have_f:
        parts.append(f"filters want={sorted(want_f)} got={sorted(have_f)}")
    if not search_ok:
        parts.append(f"search want={want_s!r} got={have_s!r}")
    if not order_ok:
        parts.append(f"ordering want={want_o!r} got={have_o!r}")
    # Right filters but a missed sort is far less bad than a wrong filter.
    verdict = "PARTIAL" if (want_f == have_f and search_ok) else "WRONG"
    return verdict, "; ".join(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--api-key", default="")
    ap.add_argument("--timeout", type=float, default=120)
    ap.add_argument("--json-schema", action="store_true",
                    help="request constrained JSON decoding (Ollama/vLLM support it)")
    ap.add_argument("--schema", default="schema.json")
    ap.add_argument("--cases", default="cases.json")
    ap.add_argument("--examples", default="",
                    help="JSON file of cases to use as few-shot examples")
    ap.add_argument("--n-examples", type=int, default=5)
    ap.add_argument("--balanced-examples", action="store_true",
                    help="weight the few-shot set toward refusals")
    ap.add_argument("--strict-values", action="store_true",
                    help="per-field value enums via oneOf — makes an invalid value undecodable")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    global SCHEMA, VALID_FIELDS, VALID_VALUES, CASES
    SCHEMA = json.loads((HERE / args.schema).read_text())
    CASES = json.loads((HERE / args.cases).read_text())
    VALID_FIELDS = {f["name"] for f in SCHEMA["filter_fields"]}
    VALID_VALUES = {f["name"]: set(f.get("choices") or f.get("presets") or [])
                    for f in SCHEMA["filter_fields"]}
    if args.strict_values:
        variants = []
        for f in SCHEMA["filter_fields"]:
            vals = list(f.get("choices") or f.get("presets") or [])
            # Ollama's grammar honours `enum` but not a nested anyOf/pattern, so an
            # exact YYYY-MM-DD cannot be allowed structurally here. Presets only;
            # exact dates would need runtime pattern support or a validate+retry pass.
            value_schema = {"type": "string", "enum": vals}
            variants.append({"type": "object", "required": ["field", "value"],
                             "properties": {"field": {"const": f["name"]}, "value": value_schema}})
        OUTPUT_SCHEMA["properties"]["filters"]["items"] = {"oneOf": variants}
    else:
        OUTPUT_SCHEMA["properties"]["filters"]["items"]["properties"]["field"]["enum"] = sorted(VALID_FIELDS)
    shots = []
    if args.examples:
        pool = json.loads((HERE / args.examples).read_text())
        # Cover the main shapes rather than the first N: status, start-date,
        # finish-date, search, and one refusal.
        want = (["status", "date", "search", "trap-range", "trap-field"]
                if not args.balanced_examples
                else ["status", "date", "trap-range", "trap-field", "trap-value"])
        for cat in want:
            for c in pool:
                if c in shots:
                    continue
                if c["cat"].startswith(cat) and len(shots) < args.n_examples:
                    shots.append(c)
                    break
    prompt = build_prompt(SCHEMA)
    if shots:
        rendered = []
        for c in shots:
            if c["expressible"]:
                exp = {"search": c["expect"]["search"], "filters": c["expect"]["filters"],
                       "ordering": c["expect"]["ordering"], "unsupported": []}
            else:
                exp = {"search": "", "filters": [], "ordering": None,
                       "unsupported": [c["text"]]}
            rendered.append(f'User: {c["text"]}\nYou: {json.dumps(exp, ensure_ascii=False)}')
        prompt += "\n\nEXAMPLES:\n" + "\n".join(rendered)
        print(f"  ({len(shots)} few-shot pelda, +{sum(len(r) for r in rendered)} karakter)\n")
    results, tally, times = [], {}, []
    print(f"model={args.model}  cases={len(CASES)}  json_schema={args.json_schema}\n")

    for case in CASES:
        try:
            raw, dt = call(args.base_url, args.model, args.api_key, prompt,
                           case["text"], args.timeout, args.json_schema)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as e:
            detail = getattr(e, "read", lambda: b"")()[:200].decode(errors="replace") if hasattr(e, "read") else ""
            print(f"  ! request failed: {e} {detail}")
            sys.exit(2)
        except (KeyError, json.JSONDecodeError) as e:
            print(f"  ! unexpected response shape: {e}")
            sys.exit(2)
        times.append(dt)
        got = parse(raw)
        verdict, detail = score(case, got)
        tally[verdict] = tally.get(verdict, 0) + 1
        mark = {"OK": "✓", "PARTIAL": "~", "WRONG": "✗", "HALLUCINATED": "!!", "UNPARSABLE": "??"}[verdict]
        print(f"{mark} [{case['id']:>2}] {case['text'][:52]:<52} {verdict:<13} {detail[:70]}")
        results.append({"case": case, "raw": raw, "parsed": got,
                        "verdict": verdict, "detail": detail, "seconds": round(dt, 2)})

    n = len(CASES)
    ok, partial = tally.get("OK", 0), tally.get("PARTIAL", 0)
    times.sort()
    print(f"\n  OK {ok}/{n} ({ok / n:.0%})   +PARTIAL {(ok + partial) / n:.0%}")
    for v in ("WRONG", "HALLUCINATED", "UNPARSABLE"):
        if tally.get(v):
            print(f"  {v}: {tally[v]}")
    print(f"  latency: median {times[len(times) // 2]:.1f}s  max {times[-1]:.1f}s")
    print("\n  Bar for shipping: 0 HALLUCINATED, 0 UNPARSABLE, OK >= 80%.")

    if args.out:
        pathlib.Path(args.out).write_text(json.dumps(
            {"model": args.model, "json_schema": args.json_schema,
             "tally": tally, "median_seconds": times[len(times) // 2],
             "results": results}, ensure_ascii=False, indent=2))
        print(f"  wrote {args.out}")


if __name__ == "__main__":
    main()
