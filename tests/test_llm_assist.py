"""The LLM assistant: it must be off by default, gated, and never trust the model.

No network here — a fake provider stands in for the LLM, so these tests assert
the *guardrails*, which is where the risk lives.
"""

import json

import pytest
from django.contrib.auth.models import Permission, User
from django.test import Client, override_settings

from theia_ng import llm
from theia_ng.llm import assist as A
from theia_ng.llm.base import LLMError, LLMProvider
from theia_ng.registry import site
from tests.testproject.sampleapp.models import Category, Stock

URL = "/theia/api/assist/sampleapp.stock/"

# A working config, pointed at the fake provider below.
LLM_ON = {"LLM": {"PROVIDER": "tests.test_llm_assist.FakeProvider",
                  "MODEL": "fake-1", "BASE_URL": "http://x/v1"}}


class FakeProvider(LLMProvider):
    """Returns whatever the test queued, without touching the network."""

    supports_schema = True
    reply = '{"search":"","filters":[],"ordering":null,"unsupported":[]}'
    seen: list[tuple[str, str]] = []

    def complete(self, system, user, schema):
        FakeProvider.seen.append((system, user))
        return FakeProvider.reply


@pytest.fixture(autouse=True)
def _reset():
    FakeProvider.seen = []
    FakeProvider.reply = '{"search":"","filters":[],"ordering":null,"unsupported":[]}'


@pytest.fixture
def client_with_access(db):
    """Superuser — the normal caller. Permission gating has its own tests."""
    c = Client()
    c.force_login(User.objects.create_user("root", password="x", is_superuser=True))
    return c


@pytest.fixture
def client_access_only(db):
    """Has theia access but no per-model view permission."""
    u = User.objects.create_user("joe", password="x")
    u.user_permissions.add(
        Permission.objects.get(codename="access", content_type__app_label="theia_ng")
    )
    c = Client()
    c.force_login(u)
    return c


def _post(client, prompt="a mai aktív tételek"):
    return client.post(URL, data=json.dumps({"prompt": prompt}),
                       content_type="application/json")


def _slice():
    model, admin = site.get_model("sampleapp.stock")
    return A.build_slice(model, admin, None)


# --- off by default --------------------------------------------------------
def test_disabled_by_default_404s(client_with_access):
    """No THEIA_NG['LLM'] -> the endpoint does not exist at all."""
    assert not llm.is_enabled()
    assert _post(client_with_access).status_code == 404


@override_settings(THEIA_NG=LLM_ON)
def test_enabled_when_configured(client_with_access):
    assert llm.is_enabled()
    assert _post(client_with_access).status_code == 200


def test_anonymous_is_forbidden(db):
    assert _post(Client()).status_code in (403, 302)


@override_settings(THEIA_NG=LLM_ON)
def test_model_view_permission_is_required(client_access_only):
    """Theia access alone must not open the assistant on a model the user
    cannot view — the assistant may never widen existing visibility."""
    assert _post(client_access_only).status_code == 403


# --- gating ----------------------------------------------------------------
@override_settings(THEIA_NG={"LLM": {**LLM_ON["LLM"], "ALLOW_MODELS": ["sampleapp.house"]}})
def test_allowlist_excludes_everything_else(client_with_access):
    assert _post(client_with_access).status_code == 404


@override_settings(THEIA_NG=LLM_ON)
def test_modeladmin_optout_wins(client_with_access):
    _, admin = site.get_model("sampleapp.stock")
    admin.assist = False
    try:
        assert _post(client_with_access).status_code == 404
    finally:
        admin.assist = True


# --- what leaves the server ------------------------------------------------
def test_slice_excludes_relations_and_traversals():
    """StockAdmin filters on category (FK) and house__name (traversal); neither
    may be described to the model, because both would need a guessed PK."""
    names = {f["name"] for f in _slice()["fields"]}
    assert "category" not in names
    assert "house__name" not in names
    assert {"is_active", "created_at"} <= names


@override_settings(THEIA_NG=LLM_ON)
def test_no_row_data_is_sent(client_with_access, db):
    Stock.objects.create(name="SECRET-WIDGET", quantity=1,
                         category=Category.objects.create(name="SECRET-CAT"))
    _post(client_with_access, "aktív tételek")
    system, user = FakeProvider.seen[-1]
    assert "SECRET-WIDGET" not in system + user


# --- never trust the model -------------------------------------------------
def test_validate_drops_unknown_field():
    state, rejected = A.validate(
        {"search": "", "filters": [{"field": "house__company", "value": "x"}],
         "ordering": None, "unsupported": []}, _slice())
    assert state["filters"] == []
    assert any("house__company" in r for r in rejected)


def test_validate_drops_out_of_vocabulary_value():
    state, rejected = A.validate(
        {"search": "", "filters": [{"field": "created_at", "value": "tavaly"}],
         "ordering": None, "unsupported": []}, _slice())
    assert state["filters"] == []
    assert any("tavaly" in r for r in rejected)


def test_validate_accepts_preset_and_exact_day():
    for value in ("last_7_days", "2026-03-01"):
        state, rejected = A.validate(
            {"search": "", "filters": [{"field": "created_at", "value": value}],
             "ordering": None, "unsupported": []}, _slice())
        assert state["filters"] == [{"field": "created_at", "value": value}], value
        assert rejected == []


def test_validate_drops_unknown_ordering():
    state, rejected = A.validate(
        {"search": "", "filters": [], "ordering": "; DROP TABLE", "unsupported": []}, _slice())
    assert state["ordering"] is None and rejected


def test_validate_survives_garbage():
    state, rejected = A.validate(None, _slice())
    assert state == {"intent": "filter", "search": "", "filters": [], "ordering": None,
                     "create": {}, "unsupported": []}
    assert rejected


@override_settings(THEIA_NG=LLM_ON)
def test_endpoint_reports_what_it_dropped(client_with_access):
    """A hallucinated filter must not reach the client silently."""
    FakeProvider.reply = json.dumps(
        {"search": "", "filters": [{"field": "secret_col", "value": "1"}],
         "ordering": None, "unsupported": []})
    body = _post(client_with_access).json()
    assert body["state"]["filters"] == []
    assert body["rejected"]


def test_parse_reply_tolerates_fences_and_prose():
    payload = '{"search":"x","filters":[],"ordering":null,"unsupported":[]}'
    for raw in (payload, f"```json\n{payload}\n```", f"Persze! {payload} kesz"):
        assert A.parse_reply(raw)["search"] == "x"
    assert A.parse_reply("nem json") is None


# --- input limits ----------------------------------------------------------
@override_settings(THEIA_NG=LLM_ON)
def test_empty_and_oversized_prompts_rejected(client_with_access):
    assert _post(client_with_access, "").status_code == 400
    assert _post(client_with_access, "x" * (A.MAX_PROMPT_CHARS + 1)).status_code == 400


@override_settings(THEIA_NG=LLM_ON)
def test_provider_failure_degrades_to_503(client_with_access, monkeypatch):
    def boom(self, system, user, schema):
        raise LLMError("endpoint unreachable")

    monkeypatch.setattr(FakeProvider, "complete", boom)
    assert _post(client_with_access).status_code == 503


# --- provider resolution ---------------------------------------------------
@override_settings(THEIA_NG={"LLM": {"PROVIDER": "nope", "MODEL": "m"}})
def test_unknown_provider_name_raises():
    with pytest.raises(LLMError):
        llm.resolve_provider()


@override_settings(THEIA_NG={"LLM": {"PROVIDER": "openai_compatible", "MODEL": "m"}})
def test_openai_compatible_requires_base_url():
    with pytest.raises(LLMError):
        llm.resolve_provider()


# --- delete / create proposals ---------------------------------------------
def _create_fields():
    model, admin = site.get_model("sampleapp.stock")
    return A.build_create_slice(model, admin)


def test_unqualified_delete_is_refused():
    """A delete with nothing identifying it would match every row. It must never
    even be *proposed* — an unqualified wipe has to be deliberate."""
    state, rejected = A.validate(
        {"intent": "delete", "search": "", "filters": [], "ordering": None,
         "create": {}, "unsupported": []}, _slice())
    assert state["intent"] == "filter"
    assert any("refusing" in r for r in rejected)


def test_qualified_delete_survives():
    state, rejected = A.validate(
        {"intent": "delete", "search": "", "ordering": None, "create": {}, "unsupported": [],
         "filters": [{"field": "is_active", "value": "false"}]}, _slice())
    assert state["intent"] == "delete" and state["filters"]


def test_unknown_intent_falls_back_to_filter():
    state, rejected = A.validate(
        {"intent": "drop_table", "search": "x", "filters": [], "ordering": None,
         "create": {}, "unsupported": []}, _slice())
    assert state["intent"] == "filter" and rejected


def test_create_slice_excludes_relations_and_readonly():
    names = {f["name"] for f in _create_fields()}
    assert "category" not in names and "spaces" not in names  # relations
    assert {"name", "quantity", "status"} <= names


def test_create_drops_unknown_and_illegal_values():
    cf = _create_fields()
    state, rejected = A.validate(
        {"intent": "create", "search": "", "filters": [], "ordering": None, "unsupported": [],
         "create": {"name": "Csavar", "secret": "x", "status": "archived"}}, _slice(), cf)
    assert state["create"] == {"name": "Csavar"}
    assert any("secret" in r for r in rejected)
    assert any("archived" in r for r in rejected)


def test_create_with_nothing_usable_is_not_a_create():
    cf = _create_fields()
    state, rejected = A.validate(
        {"intent": "create", "search": "", "filters": [], "ordering": None,
         "unsupported": [], "create": {"nope": "1"}}, _slice(), cf)
    assert state["intent"] == "filter"


@override_settings(THEIA_NG=LLM_ON)
def test_delete_proposal_carries_the_real_queryset(client_with_access, db):
    """The confirmation must be checkable against reality: exact count + rows."""
    cat = Category.objects.create(name="c")
    for i in range(3):
        Stock.objects.create(name=f"s{i}", quantity=1, category=cat, is_active=False)
    Stock.objects.create(name="keep", quantity=1, category=cat, is_active=True)
    FakeProvider.reply = json.dumps(
        {"intent": "delete", "search": "", "ordering": None, "create": {}, "unsupported": [],
         "filters": [{"field": "is_active", "value": "false"}]})
    body = _post(client_with_access, "töröld az inaktívakat").json()
    assert body["state"]["intent"] == "delete"
    assert body["preview"]["count"] == 3
    assert len(body["preview"]["rows"]) == 3
    # Proposing must not delete anything by itself.
    assert Stock.objects.count() == 4


@override_settings(THEIA_NG=LLM_ON)
def test_delete_matching_nothing_downgrades(client_with_access, db):
    FakeProvider.reply = json.dumps(
        {"intent": "delete", "search": "", "ordering": None, "create": {}, "unsupported": [],
         "filters": [{"field": "is_active", "value": "false"}]})
    body = _post(client_with_access, "töröld az inaktívakat").json()
    assert body["state"]["intent"] == "filter"


@override_settings(THEIA_NG=LLM_ON)
def test_delete_needs_delete_permission(client_access_only, db):
    """Without delete permission the proposal is downgraded, never offered."""
    u = User.objects.get(username="joe")
    u.user_permissions.add(Permission.objects.get(codename="view_stock"))
    FakeProvider.reply = json.dumps(
        {"intent": "delete", "search": "", "ordering": None, "create": {}, "unsupported": [],
         "filters": [{"field": "is_active", "value": "false"}]})
    body = _post(client_access_only, "töröld").json()
    assert body["state"]["intent"] == "filter"
    assert any("not permitted" in r for r in body["rejected"])


# --- hints / dictionary / examples ------------------------------------------
def test_hints_absent_by_default(db):
    """The tables ship empty: a fresh deploy gets no extra prompt prose."""
    h = A.load_hints("sampleapp.stock")
    assert h == {"model": "", "fields": {}, "terms": []}
    assert "hint" not in _slice()["fields"][0]


def test_field_hint_reaches_the_prompt(db):
    from theia_ng.models import AssistHint

    AssistHint.objects.create(kind="field", model_key="sampleapp.stock",
                              field_name="is_active", text="Aktív-e a tétel.")
    sl = _slice()
    assert any(f.get("hint") == "Aktív-e a tétel." for f in sl["fields"])
    assert "Aktív-e a tétel." in A.build_prompt(sl)


def test_model_hint_and_dictionary_reach_the_prompt(db):
    from theia_ng.models import AssistHint

    AssistHint.objects.create(kind="model", model_key="sampleapp.stock", text="Raktári tétel.")
    AssistHint.objects.create(kind="term", model_key="", term="cucc", text="raktári tételt jelent")
    prompt = A.build_prompt(_slice())
    assert "Raktári tétel." in prompt
    assert "cucc" in prompt and "VOCABULARY" in prompt


def test_disabled_hints_are_ignored(db):
    from theia_ng.models import AssistHint

    AssistHint.objects.create(kind="model", model_key="sampleapp.stock",
                              text="NEM KELL", enabled=False)
    assert A.load_hints("sampleapp.stock")["model"] == ""


def test_hints_for_another_model_do_not_leak(db):
    from theia_ng.models import AssistHint

    AssistHint.objects.create(kind="model", model_key="sampleapp.house", text="HÁZ")
    assert A.load_hints("sampleapp.stock")["model"] == ""


def test_hint_budget_is_enforced(db):
    """Prose measurably degrades a small model, so the prompt cannot be grown
    without bound by whoever edits the table."""
    from theia_ng.models import AssistHint

    for i in range(40):
        AssistHint.objects.create(kind="term", model_key="", term=f"t{i:02d}", text="x" * 100)
    total = sum(len(v) for _, v in A.load_hints("sampleapp.stock")["terms"])
    assert total <= A.MAX_HINT_CHARS


def test_examples_only_enter_the_prompt_when_opted_in(db):
    from theia_ng.models import AssistExample

    exp = {"intent": "filter", "search": "", "ordering": None,
           "filters": [{"field": "is_active", "value": "false"}]}
    AssistExample.objects.create(model_key="sampleapp.stock", prompt="inaktívak",
                                 expected=exp, in_prompt=False)
    assert A.load_examples("sampleapp.stock") == []
    # …but it is still available as a regression case.
    assert len(A.load_examples("sampleapp.stock", for_prompt=False)) == 1

    AssistExample.objects.filter(prompt="inaktívak").update(in_prompt=True)
    assert "inaktívak" in A.build_prompt(_slice())


def test_schema_reports_per_model_availability(db):
    """The SPA hides the entry point from this flag, so it must track the gating —
    a global "LLM configured" flag would put a button on every page, including
    models where the endpoint 404s."""
    from theia_ng.introspection import build_model_detail

    model, admin = site.get_model("sampleapp.stock")
    with override_settings(THEIA_NG=LLM_ON):
        assert build_model_detail(model, admin, None)["assist"] is True
    with override_settings(THEIA_NG={"LLM": {**LLM_ON["LLM"],
                                            "ALLOW_MODELS": ["sampleapp.house"]}}):
        assert build_model_detail(model, admin, None)["assist"] is False
    # No LLM configured at all.
    assert build_model_detail(model, admin, None)["assist"] is False


def test_assist_flag_is_not_cached_with_the_structure(db):
    """The IR is cached for SCHEMA_TTL. If `assist` were cached with it, turning
    the assistant on or off would leave the entry point lying for minutes."""
    from theia_ng.introspection import build_model_detail

    model, admin = site.get_model("sampleapp.stock")
    with override_settings(THEIA_NG=LLM_ON):
        assert build_model_detail(model, admin, None)["assist"] is True
    # Same process, same cached structure, config flipped — must follow at once.
    assert build_model_detail(model, admin, None)["assist"] is False


def test_assistant_tables_are_not_assistable(db):
    """The assistant must not be steerable through itself."""
    for key in ("theia_ng.assisthint", "theia_ng.assistexample"):
        _, admin = site.get_model(key)
        assert admin.assist is False


# --- audit trail -------------------------------------------------------------
@override_settings(THEIA_NG=LLM_ON)
def test_every_prompt_is_logged(client_with_access, db):
    """Who asked for what — recorded whatever the prompt turned into."""
    from theia_ng.models import LogEntry

    _post(client_with_access, "az inaktív tételek")
    entry = LogEntry.objects.get(action="assist")
    assert entry.username == "root"
    assert entry.model_key == "sampleapp.stock"
    assert entry.object_repr == "az inaktív tételek"
    assert entry.changes["prompt"] == "az inaktív tételek"
    assert entry.changes["intent"] == "filter"
    assert entry.changes["llm_model"] == "fake-1"


@override_settings(THEIA_NG=LLM_ON)
def test_a_refused_proposal_is_still_logged(client_with_access, db):
    """An instruction that was downgraded must still appear in the trail —
    otherwise 'what did they try to do' has a hole in it."""
    from theia_ng.models import LogEntry

    FakeProvider.reply = json.dumps(
        {"intent": "delete", "search": "", "ordering": None, "create": {}, "unsupported": [],
         "filters": []})
    _post(client_with_access, "töröld ki az összeset")
    entry = LogEntry.objects.get(action="assist")
    assert entry.changes["intent"] == "filter"          # downgraded
    assert entry.changes["rejected"]                    # and why
    assert entry.object_repr == "töröld ki az összeset"


@override_settings(THEIA_NG=LLM_ON)
def test_delete_proposal_logs_the_match_count(client_with_access, db):
    from theia_ng.models import LogEntry

    cat = Category.objects.create(name="c")
    Stock.objects.create(name="s", quantity=1, category=cat, is_active=False)
    FakeProvider.reply = json.dumps(
        {"intent": "delete", "search": "", "ordering": None, "create": {}, "unsupported": [],
         "filters": [{"field": "is_active", "value": "false"}]})
    _post(client_with_access, "töröld az inaktívakat")
    entry = LogEntry.objects.get(action="assist")
    assert entry.changes["intent"] == "delete"
    assert entry.changes["match_count"] == 1


def test_logging_never_breaks_the_request(client_with_access, db, monkeypatch):
    """Auditing is best-effort everywhere else in theia; keep it that way here."""
    import theia_ng.audit as audit_mod

    def boom(*a, **kw):
        raise RuntimeError("db gone")

    monkeypatch.setattr(audit_mod, "record", boom)
    with override_settings(THEIA_NG=LLM_ON):
        assert _post(client_with_access).status_code == 200
