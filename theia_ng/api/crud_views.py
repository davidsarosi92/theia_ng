"""Generic auto-CRUD data endpoints.

The default data layer: operates directly on the ORM (like django admin),
guarded by the per-model ModelAdmin permission hooks. Saves run inside a
transaction and go through ``full_clean()`` so model validation and ORM signals
behave exactly as elsewhere in the project.

Endpoints (under ``<prefix>api/``):
* ``GET    data/<app.model>/``         list (paginated, searchable, filterable)
* ``POST   data/<app.model>/``         create
* ``GET    data/<app.model>/<pk>/``    retrieve
* ``PATCH  data/<app.model>/<pk>/``    update
* ``DELETE data/<app.model>/<pk>/``    delete
* ``POST   action/<app.model>/<key>/`` custom action

The same list endpoint backs FK/M2M option lookups (the IR's ``options_endpoint``),
so ``?search=`` is honoured against ``search_fields``.

NOTE on CSRF: these use session auth (same origin), so unsafe methods require a
CSRF token. The SPA must send ``X-CSRFToken``; we do NOT csrf_exempt.

NOTE on DRF delegation: if a DRF adapter is registered for a model, these views
should defer to it (theia_ng.adapters). Not wired yet — generic path only.
"""

from __future__ import annotations

import json
from typing import Any

from django.core.exceptions import FieldError
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404, HttpRequest, JsonResponse
from django.views import View

from theia_ng.adapters import AdapterValidationError, resolve_adapter
from theia_ng.api.serialization import relation_field_names, serializable_fields
from theia_ng.permissions import has_access
from theia_ng.registry import site


def _forbidden() -> JsonResponse:
    return JsonResponse({"detail": "Forbidden"}, status=403)


def _json_body(request: HttpRequest) -> dict[str, Any] | None:
    try:
        return json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


def _validation_response(exc: AdapterValidationError) -> JsonResponse:
    return JsonResponse({"errors": exc.errors}, status=400)


class _BaseModelView(View):
    """Resolves the model + admin (+ data adapter) and enforces the access gate."""

    model = None
    admin = None
    adapter = None

    def dispatch(self, request: HttpRequest, *args, **kwargs):
        if not has_access(request):
            return _forbidden()
        resolved = site.get_model(kwargs["model_key"])
        if resolved is None:
            raise Http404(f"Model {kwargs['model_key']!r} is not registered")
        self.model, self.admin = resolved
        self.adapter = resolve_adapter(self.model, self.admin)
        return super().dispatch(request, *args, **kwargs)


class DataListView(_BaseModelView):
    def get(self, request: HttpRequest, model_key: str):
        if not self.admin.has_view_permission(request):
            return _forbidden()

        fk_names, m2m_names = relation_field_names(serializable_fields(self.model))
        qs = self.adapter.get_queryset()
        if fk_names:
            qs = qs.select_related(*fk_names)
        if m2m_names:
            qs = qs.prefetch_related(*m2m_names)

        # search
        search = request.GET.get("search")
        if search and self.admin.search_fields:
            q = Q()
            for name in self.admin.search_fields:
                q |= Q(**{f"{name}__icontains": search})
            qs = qs.filter(q)

        # filters
        try:
            for name in self.admin.list_filter:
                if name in request.GET:
                    qs = qs.filter(**{name: request.GET[name]})

            # ordering
            ordering = request.GET.get("ordering")
            if ordering:
                qs = qs.order_by(*ordering.split(","))
            elif self.admin.ordering:
                qs = qs.order_by(*self.admin.ordering)
            else:
                # Stable default so pagination is consistent (e.g. the relation
                # combobox loading pages as you scroll thousands of rows).
                qs = qs.order_by("pk")

            paginator = Paginator(qs, self.admin.list_per_page)
            page = paginator.get_page(request.GET.get("page", 1))
            results = [self.adapter.to_representation(obj) for obj in page]
        except (FieldError, ValueError) as exc:
            return JsonResponse({"detail": str(exc)}, status=400)

        return JsonResponse(
            {
                "count": paginator.count,
                "page": page.number,
                "num_pages": paginator.num_pages,
                "results": results,
            }
        )

    def post(self, request: HttpRequest, model_key: str):
        if not self.admin.has_add_permission(request):
            return _forbidden()
        data = _json_body(request)
        if data is None:
            return JsonResponse({"detail": "Invalid JSON body"}, status=400)
        try:
            instance = self.adapter.save(self.model(), data)
        except AdapterValidationError as exc:
            return _validation_response(exc)
        return JsonResponse(self.adapter.to_representation(instance), status=201)


class DataDetailView(_BaseModelView):
    def _get_object(self, pk):
        try:
            return self.model._default_manager.get(pk=pk)
        except self.model.DoesNotExist:
            raise Http404(f"{self.model._meta.object_name} {pk!r} not found")

    def get(self, request: HttpRequest, model_key: str, pk: str):
        if not self.admin.has_view_permission(request):
            return _forbidden()
        instance = self._get_object(pk)
        return JsonResponse(self.adapter.to_representation(instance))

    def patch(self, request: HttpRequest, model_key: str, pk: str):
        if not self.admin.has_change_permission(request):
            return _forbidden()
        data = _json_body(request)
        if data is None:
            return JsonResponse({"detail": "Invalid JSON body"}, status=400)
        instance = self._get_object(pk)
        try:
            instance = self.adapter.save(instance, data, partial=True)
        except AdapterValidationError as exc:
            return _validation_response(exc)
        return JsonResponse(self.adapter.to_representation(instance))

    def delete(self, request: HttpRequest, model_key: str, pk: str):
        if not self.admin.has_delete_permission(request):
            return _forbidden()
        instance = self._get_object(pk)
        instance.delete()
        return JsonResponse({}, status=204)


class ActionView(_BaseModelView):
    """Run a custom ModelAdmin action over a selection of objects.

    The action is a method on the ModelAdmin named in ``admin.actions``, with the
    signature ``method(request, queryset)`` (django-admin style).
    """

    def post(self, request: HttpRequest, model_key: str, action_key: str):
        if action_key not in self.admin.actions:
            raise Http404(f"Action {action_key!r} is not registered")
        if not self.admin.has_change_permission(request):
            return _forbidden()

        method = getattr(self.admin, action_key, None)
        if not callable(method):
            return JsonResponse({"detail": "Action not implemented"}, status=501)

        body = _json_body(request) or {}
        queryset = self.model._default_manager.filter(pk__in=body.get("ids", []))
        result = method(request, queryset)
        return JsonResponse(
            {
                "detail": "ok",
                "result": result if isinstance(result, (dict, list, str, int, float, bool)) else None,
            }
        )
