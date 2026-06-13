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

from django.core.exceptions import FieldDoesNotExist, FieldError
from django.core.paginator import Paginator
from django.db import models
from django.db.models import Q
from django.http import Http404, HttpRequest, JsonResponse
from django.views import View

from theia_ng import audit
from theia_ng.adapters import AdapterValidationError, resolve_adapter
from theia_ng.api.serialization import (
    relation_field_names,
    scalar_and_fk_fields,
    serializable_fields,
    serialize_option,
)
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


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _filter_field(model, name: str):
    """Resolve a filter name (possibly ``a__b``) to its leaf Django field, or None."""
    cur = model
    field = None
    for i, part in enumerate(name.split("__")):
        try:
            field = cur._meta.get_field(part)
        except (FieldDoesNotExist, AttributeError):
            return None
        if i < len(name.split("__")) - 1:
            cur = getattr(field, "related_model", None)
            if cur is None:
                return None
    return field


# Relative date presets: how many days back from now (None = exact day "today").
_DATE_PRESETS = {"today": None, "last_2_days": 2, "last_7_days": 7, "last_30_days": 30, "last_year": 365}


def _apply_date_filter(qs, name: str, field, value: str):
    """Apply a date/datetime filter: a preset keyword, an ISO date (``YYYY-MM-DD``,
    time optional), or an exact value."""
    import datetime
    import re

    from django.utils import timezone

    is_dt = isinstance(field, models.DateTimeField)

    if value in _DATE_PRESETS:
        days = _DATE_PRESETS[value]
        if days is None:  # today
            today = timezone.localdate()
            return qs.filter(**{f"{name}__date" if is_dt else name: today})
        if is_dt:
            return qs.filter(**{f"{name}__gte": timezone.now() - datetime.timedelta(days=days)})
        return qs.filter(**{f"{name}__gte": timezone.localdate() - datetime.timedelta(days=days)})

    # Specific calendar day (time optional): match the date part.
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value or ""):
        return qs.filter(**{f"{name}__date" if is_dt else name: value})

    return qs.filter(**{name: value})


def _custom_filter_instances(admin) -> list:
    """Instances of the custom ListFilter subclasses declared in ``list_filter``."""
    from theia_ng.filters import ListFilter

    return [f() for f in admin.list_filter if isinstance(f, type) and issubclass(f, ListFilter)]


def _resolve_lookup(obj, path: str) -> Any:
    """Follow a ``house__company__name`` lookup across relations, None-safe."""
    cur = obj
    for part in path.split("__"):
        if cur is None:
            return None
        cur = getattr(cur, part, None)
    return cur


def _apply_list_display(admin, obj, representation: dict[str, Any]) -> None:
    """Add computed ``list_display`` columns (admin methods, model attrs, or
    ``a__b`` relation lookups) to a serialized row. Real model fields are already
    present from the adapter."""
    for name in admin.list_display:
        method = getattr(admin, name, None)
        if callable(method):  # ModelAdmin method: method(obj)
            try:
                representation[name] = _jsonable(method(obj))
            except Exception:
                representation[name] = None
        elif "__" in name:  # relation-spanning lookup
            try:
                representation[name] = _jsonable(_resolve_lookup(obj, name))
            except Exception:
                representation[name] = None
        elif name not in representation:  # model property / method / attribute
            attr = getattr(obj, name, None)
            try:
                representation[name] = _jsonable(attr() if callable(attr) else attr)
            except Exception:
                representation[name] = None


def _list_display_relation_paths(admin) -> list[str]:
    """Relation prefixes of ``a__b`` list_display columns, for select_related
    (e.g. ``house__company__name`` -> ``house__company``)."""
    paths = []
    for name in admin.list_display:
        if "__" in name and not callable(getattr(admin, name, None)):
            paths.append(name.rsplit("__", 1)[0])
    return paths


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
        qs = self.admin.get_queryset(request)
        # select_related: direct FKs (cheap joins, help relation labels) + the
        # relation prefixes of any a__b columns + list_select_related.
        related = list(dict.fromkeys([
            *fk_names,
            *_list_display_relation_paths(self.admin),
            *self.admin.list_select_related,
        ]))
        if related:
            qs = qs.select_related(*related)
        # prefetch ONLY the M2M actually shown as a column (+ declared ones) — a
        # non-displayed M2M must never be materialized per row in a list.
        displayed = set(self.admin.list_display)
        shown_m2m = [n for n in m2m_names if n in displayed]
        prefetch = list(dict.fromkeys([*shown_m2m, *self.admin.list_prefetch_related]))
        if prefetch:
            qs = qs.prefetch_related(*prefetch)

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
                if not isinstance(name, str):
                    continue  # custom ListFilter classes are applied below
                if name not in request.GET:
                    continue
                value: object = request.GET[name]
                field = _filter_field(self.model, name)
                if isinstance(field, models.BooleanField):
                    qs = qs.filter(**{name: str(value).lower() in ("true", "1", "yes", "on")})
                elif isinstance(field, (models.DateField, models.DateTimeField)):
                    qs = _apply_date_filter(qs, name, field, str(value))
                else:
                    qs = qs.filter(**{name: value})

            # custom filters (theia_ng.ListFilter subclasses in list_filter)
            for flt in _custom_filter_instances(self.admin):
                if flt.parameter_name in request.GET:
                    qs = flt.queryset(request, qs, request.GET[flt.parameter_name])

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
            results = []
            for obj in page:
                rep = self.adapter.to_list_representation(obj, self.admin.list_display)
                _apply_list_display(self.admin, obj, rep)
                results.append(rep)
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
        rep = self.adapter.to_representation(instance)
        audit.record(
            request,
            "create",
            model_key,
            object_pk=instance.pk,
            object_repr=self.admin.display(instance),
            changes=audit.diff({}, rep),
        )
        return JsonResponse(rep, status=201)


class DataDetailView(_BaseModelView):
    def _get_object(self, request: HttpRequest, pk):
        # Through the admin's queryset, so row scoping (e.g. tenant) also hides
        # objects from detail/update/delete, not just the list.
        try:
            return self.admin.get_queryset(request).get(pk=pk)
        except self.model.DoesNotExist:
            raise Http404(f"{self.model._meta.object_name} {pk!r} not found")

    def get(self, request: HttpRequest, model_key: str, pk: str):
        instance = self._get_object(request, pk)
        if not self.admin.has_view_permission(request, instance):
            return _forbidden()
        return JsonResponse(self.adapter.to_representation(instance))

    def patch(self, request: HttpRequest, model_key: str, pk: str):
        instance = self._get_object(request, pk)
        if not self.admin.has_change_permission(request, instance):
            return _forbidden()
        data = _json_body(request)
        if data is None:
            return JsonResponse({"detail": "Invalid JSON body"}, status=400)
        before = self.adapter.to_representation(instance)
        try:
            instance = self.adapter.save(instance, data, partial=True)
        except AdapterValidationError as exc:
            return _validation_response(exc)
        after = self.adapter.to_representation(instance)
        audit.record(
            request,
            "update",
            model_key,
            object_pk=instance.pk,
            object_repr=self.admin.display(instance),
            changes=audit.diff(before, after),
        )
        return JsonResponse(after)

    def delete(self, request: HttpRequest, model_key: str, pk: str):
        instance = self._get_object(request, pk)
        if not self.admin.has_delete_permission(request, instance):
            return _forbidden()
        object_repr = self.admin.display(instance)
        instance.delete()
        audit.record(request, "delete", model_key, object_pk=pk, object_repr=object_repr)
        return JsonResponse({}, status=204)


class RelationOptionsView(View):
    """Options for a relation field, narrowed by the source admin's
    ``relation_filters`` using sibling values supplied by the client.

    The filter lookups are SERVER-defined (from the source ModelAdmin); the
    client only supplies the sibling field values. If a declared sibling value
    is missing, no options are returned (the dependency must be satisfied first).
    Response shape matches the list endpoint, so the combobox consumes it as-is.
    """

    def get(self, request: HttpRequest, model_key: str, field: str):
        if not has_access(request):
            return _forbidden()
        resolved = site.get_model(model_key)
        if resolved is None:
            raise Http404(f"Model {model_key!r} is not registered")
        model, admin = resolved
        if not admin.has_view_permission(request):
            return _forbidden()

        spec = (admin.relation_filters or {}).get(field)
        if not spec:
            raise Http404(f"No relation filter declared for {field!r}")
        try:
            rel_field = model._meta.get_field(field)
        except FieldDoesNotExist:
            raise Http404(f"Unknown field {field!r}")
        target = rel_field.related_model

        filter_kwargs: dict[str, object] = {}
        missing = False
        for target_lookup, source_field in spec.items():
            value = request.GET.get(source_field)
            if value in (None, ""):
                missing = True
                break
            filter_kwargs[target_lookup] = value

        # Options only need pk + label (a scalar/__str__), never the target's
        # M2M — so select_related FKs (for labels) but don't prefetch M2M.
        option_fields = scalar_and_fk_fields(target)
        if missing:
            qs = target._default_manager.none()
        else:
            qs = target._default_manager.filter(**filter_kwargs)
            fk_names, _m2m = relation_field_names(option_fields)
            if fk_names:
                qs = qs.select_related(*fk_names)

        target_resolved = site.get_model(f"{target._meta.app_label}.{target._meta.model_name}")
        target_admin = target_resolved[1] if target_resolved else None

        search = request.GET.get("search")
        if search and target_admin and target_admin.search_fields:
            q = Q()
            for name in target_admin.search_fields:
                q |= Q(**{f"{name}__icontains": search})
            qs = qs.filter(q)

        try:
            qs = qs.order_by("pk")
            per_page = target_admin.list_per_page if target_admin else 50
            paginator = Paginator(qs, per_page)
            page = paginator.get_page(request.GET.get("page", 1))
            results = [serialize_option(obj, target, target_admin) for obj in page]
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


class TreeView(_BaseModelView):
    """The hierarchy tree rooted at a record's topmost ancestor.

    Walks up ``tree_parent`` to the root, then down ``tree_children``, returning
    a nested structure with per-node object-level perms. The opened record is
    flagged ``is_current`` so the SPA can highlight it.
    """

    def get(self, request: HttpRequest, model_key: str, pk: str):
        from theia_ng.introspection.tree import build_tree

        try:
            instance = self.admin.get_queryset(request).get(pk=pk)
        except self.model.DoesNotExist:
            raise Http404(f"{self.model._meta.object_name} {pk!r} not found")
        if not self.admin.has_view_permission(request, instance):
            return _forbidden()
        return JsonResponse(build_tree(self.model, self.admin, instance, request))


class TreeChildrenView(_BaseModelView):
    """One child group of a tree node — searched and paginated.

    Backs the lazy mini-tables: ``?page=`` and ``?search=`` page/filter the
    children, ``?focus=<pk>`` jumps to the page holding that child (so the SPA
    can auto-expand the lineage down to the opened record).
    """

    def get(self, request: HttpRequest, model_key: str, pk: str, accessor: str):
        from theia_ng.introspection.tree import ChildAccessDenied, build_children

        try:
            instance = self.admin.get_queryset(request).get(pk=pk)
        except self.model.DoesNotExist:
            raise Http404(f"{self.model._meta.object_name} {pk!r} not found")
        if not self.admin.has_view_permission(request, instance):
            return _forbidden()
        if accessor not in (self.admin.tree_children or []):
            raise Http404(f"{accessor!r} is not a tree child of {model_key}")

        try:
            page = int(request.GET.get("page", 1) or 1)
        except ValueError:
            page = 1
        try:
            data = build_children(
                self.model,
                self.admin,
                instance,
                accessor,
                request,
                page=page,
                search=request.GET.get("search", "") or "",
                focus=request.GET.get("focus") or None,
            )
        except LookupError:
            raise Http404(f"Unknown child relation {accessor!r}")
        except ChildAccessDenied:
            return _forbidden()
        return JsonResponse(data)


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
        ids = body.get("ids", [])
        params = body.get("params", {}) or {}
        queryset = self.model._default_manager.filter(pk__in=ids)

        # Parameterized actions (declared with @theia_ng.action) validate their
        # required fields and receive the collected params as a third argument.
        meta = getattr(method, "_theia_action", None)
        if meta:
            errors = {
                f.name: ["This field is required."]
                for f in meta["fields"]
                if f.required and params.get(f.name) in (None, "", [], {})
            }
            if errors:
                return JsonResponse({"errors": errors}, status=400)
            result = method(request, queryset, params)
        else:
            result = method(request, queryset)
        audit.record(
            request,
            "action",
            model_key,
            object_repr=f"{action_key} ({len(ids)} objects)",
            changes={"action": action_key, "ids": [str(i) for i in ids], "params": params},
        )
        return JsonResponse(
            {
                "detail": "ok",
                "result": result if isinstance(result, (dict, list, str, int, float, bool)) else None,
            }
        )
