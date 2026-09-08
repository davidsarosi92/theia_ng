"""The assistant endpoint: ``POST <prefix>api/assist/<app.model>/``.

**Read-only by construction.** It takes a sentence and returns a *filter state*
— the same ``{search, filters, ordering}`` the filter dialog produces. It never
touches data. Applying the filter, and any delete that follows, go through the
existing list/action views with their own permission checks and audit trail.

It classifies the request as *filter*, *delete* or *create* and returns a
**proposal**. A delete proposal carries the exact matching count and a sample of
the rows, so the confirmation modal shows the real queryset rather than a
description of it. Carrying a proposal out is a separate, deliberate call by the
UI to the endpoints that already exist — ``action/<key>/delete_selected/`` and
``POST data/<key>/`` — each with its own permission check and audit record.

Request::   {"prompt": "a múlt heti megszakított ívek"}
Response::  {"state": {...}, "preview": {...}, "rejected": [...], "llm_model": "..."}

``404`` when the feature is off or not allowed for this model, so a disabled
deployment exposes no surface at all.
"""

from __future__ import annotations

import json

from django.http import Http404, HttpRequest, JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_protect
from django.utils.decorators import method_decorator

from theia_ng import audit, llm
from theia_ng.llm import assist as assist_mod
from theia_ng.permissions import has_access
from theia_ng.registry import site


@method_decorator(csrf_protect, name="dispatch")
class AssistView(View):
    """Turn a natural-language request into a validated list state."""

    def post(self, request: HttpRequest, model_key: str) -> JsonResponse:
        if not has_access(request):
            return JsonResponse({"detail": "Forbidden"}, status=403)
        if not llm.is_enabled():
            raise Http404("The assistant is not configured")

        match = site.get_model(model_key)
        if match is None:
            raise Http404(f"Model {model_key!r} is not registered")
        model, admin = match
        self.model, self.admin = model, admin

        # The assistant may never widen what a user can already see.
        if not admin.has_view_permission(request):
            return JsonResponse({"detail": "Forbidden"}, status=403)
        if not llm.model_allowed(model_key, admin):
            raise Http404("The assistant is not enabled for this model")

        try:
            body = json.loads(request.body or b"{}")
        except json.JSONDecodeError:
            return JsonResponse({"detail": "Invalid JSON body"}, status=400)
        prompt = (body.get("prompt") or "").strip()
        if not prompt:
            return JsonResponse({"detail": "Empty prompt"}, status=400)
        if len(prompt) > assist_mod.MAX_PROMPT_CHARS:
            return JsonResponse(
                {"detail": f"Prompt longer than {assist_mod.MAX_PROMPT_CHARS} characters"},
                status=400,
            )

        # Only schema metadata for the filterable columns leaves the server —
        # never row data, and never a field the user cannot already filter on.
        slice_ = assist_mod.build_slice(model, admin, request)
        # Create fields are offered to the model only when the user may actually
        # create here — otherwise the proposal could never be carried out.
        create_fields = (
            assist_mod.build_create_slice(model, admin)
            if admin.has_add_permission(request)
            else []
        )
        if not slice_["fields"] and not slice_["search_fields"]:
            return JsonResponse(
                {"detail": "This model has nothing to filter or search on"}, status=400
            )

        try:
            provider = llm.resolve_provider()
        except llm.LLMError as exc:
            return JsonResponse({"detail": str(exc)}, status=503)

        system = assist_mod.build_prompt(slice_, create_fields)
        schema = (
            assist_mod.build_response_schema(slice_, create_fields)
            if provider.supports_schema
            else None
        )
        cfg = llm.llm_config()
        attempts = max(1, int(cfg.get("MAX_RETRIES", 1)) + 1)

        state, rejected = None, []
        for attempt in range(attempts):
            try:
                raw = provider.complete(system, prompt, schema)
            except llm.LLMError as exc:
                return JsonResponse({"detail": str(exc)}, status=503)
            state, rejected = assist_mod.validate(
                assist_mod.parse_reply(raw), slice_, create_fields
            )
            # A clean parse with nothing dropped is the only reason to stop early;
            # otherwise retry once, because a provider's grammar cannot be trusted
            # to have covered the whole value space.
            if not rejected:
                break

        # An irreversible proposal must be checkable against reality, not against
        # the model's description of it. Downgrade rather than propose an action
        # the user could not perform anyway.
        preview = None
        if state["intent"] == "delete":
            if not admin.has_delete_permission(request) or not admin.list_selectable:
                state["intent"] = "filter"
                rejected.append("delete is not permitted for you on this model")
            else:
                preview = self._delete_preview(request, state)
                if preview["count"] == 0:
                    state["intent"] = "filter"

        # Record the instruction, whatever it turned into. This is the "who asked
        # for what" trail; the write itself (if the user confirms one) is audited
        # separately by the endpoint that performs it.
        # Best-effort, like every other audit call in theia: a logging problem
        # must never fail the request. `record` swallows its own errors, but
        # assembling `changes` could still raise on an odd value.
        try:
            audit.record(
                request,
                "assist",
                model_key,
                object_repr=prompt,
                changes={
                    "prompt": prompt[: assist_mod.MAX_PROMPT_CHARS],
                    "intent": state["intent"],
                    "search": state["search"],
                    "filters": state["filters"],
                    "ordering": state["ordering"],
                    "create": state["create"],
                    "unsupported": state["unsupported"],
                    "rejected": rejected,
                    "llm_model": provider.model,
                    "match_count": (preview or {}).get("count"),
                },
            )
        except Exception:
            pass

        return JsonResponse({
            "model_key": model_key,
            "state": state,
            "unsupported": state["unsupported"],
            # Named so the UI can say "I ignored part of that" instead of
            # silently presenting a narrower proposal than the user asked for.
            "rejected": rejected,
            "preview": preview,
            "llm_model": provider.model,
        })

    def _delete_preview(self, request: HttpRequest, state: dict) -> dict:
        """Exact count + a sample of the rows the delete would remove.

        Built from the *same* ``apply_list_filters`` the bulk action will use, so
        what the user confirms is what runs — not an approximation of it.
        """
        from theia_ng.api.crud_views import apply_list_filters
        from theia_ng.api.serialization import serialize_instance, scalar_and_fk_fields

        params = {f["field"]: f["value"] for f in state["filters"]}
        if state["search"]:
            params["search"] = state["search"]
        qs = apply_list_filters(
            self.admin.get_queryset(request), self.model, self.admin, params, request
        )
        count = qs.count()
        fields = scalar_and_fk_fields(self.model)
        rows = [
            serialize_instance(obj, fields, self.admin, m2m_cap=0)
            for obj in qs[: assist_mod.DELETE_PREVIEW_ROWS]
        ]
        return {"count": count, "rows": rows, "shown": len(rows)}
