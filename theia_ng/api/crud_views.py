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
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.paginator import Paginator
from django.db import models, transaction
from django.db.models import Q
from django.http import Http404, HttpRequest, JsonResponse
from django.views import View

from theia_ng import audit
from theia_ng.adapters import AdapterValidationError, resolve_adapter
from theia_ng.api.serialization import (
    apply_data,
    relation_field_names,
    scalar_and_fk_fields,
    serializable_fields,
    serialize_instance,
    serialize_option,
)
from theia_ng.api.list_optimize import select_related_paths
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


# --- inlines (related child rows edited on the parent form) -----------------


def _resolve_inlines(admin, parent_model) -> list[dict[str, Any]]:
    """Resolved inline descriptors: the inline instance, child model, the child
    FK pointing back to the parent, and the payload key (matching the IR)."""
    from theia_ng.introspection.builder import _inline_fk_name, _model_key

    out: list[dict[str, Any]] = []
    seen: dict[str, int] = {}
    for inline_cls in getattr(admin, "inlines", []) or []:
        inline = inline_cls()
        child = inline.model
        fk_name = _inline_fk_name(parent_model, child, inline.fk_name)
        if not fk_name:
            continue
        child_key = _model_key(child)
        n = seen.get(child_key, 0)
        seen[child_key] = n + 1
        out.append({
            "inline": inline,
            "child": child,
            "fk_name": fk_name,
            "key": child_key if n == 0 else f"{child_key}#{n}",
        })
    return out


def _inline_row_fields(child, inline, fk_name) -> list[models.Field]:
    from theia_ng.introspection.builder import inline_field_names

    fields: list[models.Field] = []
    for name in inline_field_names(child, inline, fk_name):
        try:
            fields.append(child._meta.get_field(name))
        except FieldDoesNotExist:
            continue
    return fields


def _serialize_inlines(admin, parent) -> dict[str, list[dict[str, Any]]]:
    """Existing child rows per inline, keyed like the IR (for the detail GET)."""
    rows: dict[str, list[dict[str, Any]]] = {}
    for spec in _resolve_inlines(admin, type(parent)):
        child, inline, fk_name = spec["child"], spec["inline"], spec["fk_name"]
        fields = _inline_row_fields(child, inline, fk_name)
        qs = child._default_manager.filter(**{fk_name: parent.pk}).order_by("pk")
        rows[spec["key"]] = [serialize_instance(obj, fields, inline) for obj in qs]
    return rows


def _save_inlines(admin, parent, data) -> None:
    """Create/update/delete child rows from ``data['inlines']`` (keyed per inline).
    Each row may carry ``pk`` (update) and ``_delete: true`` (delete); rows without
    a pk are created. The parent FK is always forced to the parent — never trusted
    from the row. Raises ``DjangoValidationError`` on an invalid child."""
    payload = (data or {}).get("inlines") or {}
    if not payload:
        return
    for spec in _resolve_inlines(admin, type(parent)):
        rows = payload.get(spec["key"])
        if not isinstance(rows, list):
            continue
        child, inline, fk_name = spec["child"], spec["inline"], spec["fk_name"]
        fk_attname = child._meta.get_field(fk_name).attname
        for row in rows:
            if not isinstance(row, dict):
                continue
            pk = row.get("pk")
            if row.get("_delete"):
                if pk and inline.can_delete:
                    child._default_manager.filter(pk=pk, **{fk_name: parent.pk}).delete()
                continue
            obj = child._default_manager.get(pk=pk) if pk else child()
            apply_data(obj, row, child, inline)
            setattr(obj, fk_attname, parent.pk)  # force parent link last
            obj.full_clean(exclude=[fk_name])
            obj.save()


def _inline_error_response(exc: DjangoValidationError) -> JsonResponse:
    detail = exc.message_dict if hasattr(exc, "message_dict") else {"__all__": list(exc.messages)}
    return JsonResponse({"errors": {"inlines": detail}}, status=400)


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


def _lookup_spawns_duplicates(model, lookup: str) -> bool:
    """True if filtering ``model`` on ``lookup`` joins a to-many relation, which
    yields duplicate rows that must be collapsed with ``.distinct()``. Mirrors
    Django admin's helper of the same name without importing ``django.contrib.admin``
    (theia_ng depends only on ``django.contrib.auth``)."""
    opts = model._meta
    for part in lookup.split("__"):
        try:
            field = opts.get_field(opts.pk.name if part == "pk" else part)
        except FieldDoesNotExist:
            continue  # query lookup (icontains, …), not a field — stop following
        path_infos = getattr(field, "path_infos", None)
        if path_infos:
            opts = path_infos[-1].to_opts
            if any(p.m2m for p in path_infos):
                return True
    return False


def apply_list_filters(qs, model, admin, params, request: HttpRequest):
    """Apply search + field/custom filters from ``params`` (a dict-like: the list
    view's ``request.GET``, or an action body's ``filters`` dict). Ordering and
    pagination stay with the caller. Shared by the list view and bulk actions so
    a "select all matching" action operates on exactly the listed rows."""
    needs_distinct = False
    search = params.get("search")
    if search and admin.search_fields:
        q = Q()
        for name in admin.search_fields:
            q |= Q(**{f"{name}__icontains": search})
        qs = qs.filter(q)
        needs_distinct = needs_distinct or any(
            _lookup_spawns_duplicates(model, name) for name in admin.search_fields
        )

    for name in admin.list_filter:
        if not isinstance(name, str) or name not in params:
            continue  # custom ListFilter classes are applied below
        value = params[name]
        field = _filter_field(model, name)
        if isinstance(field, models.BooleanField):
            qs = qs.filter(**{name: str(value).lower() in ("true", "1", "yes", "on")})
        elif isinstance(field, (models.DateField, models.DateTimeField)):
            qs = _apply_date_filter(qs, name, field, str(value))
        else:
            qs = qs.filter(**{name: value})
        needs_distinct = needs_distinct or _lookup_spawns_duplicates(model, name)

    for flt in _custom_filter_instances(admin):
        if flt.parameter_name in params:
            qs = flt.queryset(request, qs, params[flt.parameter_name])

    # A to-many join (search across a reverse FK / M2M, or such a list_filter) emits
    # one row per related match — collapse so an object appears once.
    if needs_distinct:
        qs = qs.distinct()
    return qs


def _resolve_lookup(obj, path: str) -> Any:
    """Follow a ``house__company__name`` lookup across relations, None-safe."""
    cur = obj
    for part in path.split("__"):
        if cur is None:
            return None
        cur = getattr(cur, part, None)
    return cur


def _apply_list_display(admin, obj, representation: dict[str, Any], columns) -> None:
    """Add computed ``columns`` (admin methods, model attrs, or ``a__b`` relation
    lookups) to a serialized row. Real model fields are already present from the
    adapter."""
    for name in columns:
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


def _relation_paths_for(admin, columns) -> list[str]:
    """Relation prefixes of ``a__b`` columns, for select_related
    (e.g. ``house__company__name`` -> ``house__company``)."""
    paths = []
    for name in columns:
        if "__" in name and not callable(getattr(admin, name, None)):
            paths.append(name.rsplit("__", 1)[0])
    return paths


def _requested_columns(request: HttpRequest, admin) -> list[str]:
    """Columns to serialize for this list request: the client's ``columns=``
    (a saved view's fields) if present, else the admin's ``list_display``. Limits
    the row to what's shown instead of every field — a much narrower query."""
    raw = request.GET.get("columns")
    if raw:
        return [c for c in raw.split(",") if c]
    return list(admin.list_display)


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

        columns = _requested_columns(request, self.admin)
        cols = set(columns)
        fk_names, m2m_names = relation_field_names(serializable_fields(self.model))
        qs = self.admin.get_queryset(request)
        # select_related, scoped to the shown columns only: the FKs rendered as
        # cells + the relation prefixes of any a__b columns + the forward-relation
        # paths those columns' labels traverse (auto, kills N+1) + the explicit
        # list_select_related. We do NOT join FKs that aren't shown.
        related = list(dict.fromkeys([
            *[n for n in fk_names if n in cols],
            *_relation_paths_for(self.admin, columns),
            *select_related_paths(self.model, self.admin, columns),
            *self.admin.list_select_related,
        ]))
        if related:
            qs = qs.select_related(*related)
        # prefetch ONLY the M2M actually shown as a column (+ declared ones) — a
        # non-displayed M2M must never be materialized per row in a list.
        shown_m2m = [n for n in m2m_names if n in cols]
        prefetch = list(dict.fromkeys([*shown_m2m, *self.admin.list_prefetch_related]))
        if prefetch:
            qs = qs.prefetch_related(*prefetch)

        try:
            qs = apply_list_filters(qs, self.model, self.admin, request.GET, request)

            # ordering
            ordering = request.GET.get("ordering")
            if ordering:
                qs = qs.order_by(*ordering.split(","))
            elif self.admin.ordering:
                qs = qs.order_by(*self.admin.ordering)
            else:
                # No admin ordering -> newest first by pk. Stable, so pagination
                # stays consistent (e.g. the relation combobox paging thousands).
                qs = qs.order_by("-pk")

            paginator = Paginator(qs, self.admin.list_per_page)
            page = paginator.get_page(request.GET.get("page", 1))
            # Fast batch path (fastberry) when the adapter offers one; eligibility
            # guarantees no computed columns, so no per-instance pass is needed.
            results = self.adapter.serialize_list_page(page.object_list, columns)
            if results is None:
                results = []
                for obj in page:
                    rep = self.adapter.to_list_representation(obj, columns)
                    _apply_list_display(self.admin, obj, rep, columns)
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
            with transaction.atomic():
                instance = self.adapter.save(self.model(), data)
                _save_inlines(self.admin, instance, data)
        except AdapterValidationError as exc:
            return _validation_response(exc)
        except DjangoValidationError as exc:
            return _inline_error_response(exc)
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
        rep = self.adapter.to_representation(instance)
        if getattr(self.admin, "inlines", None):
            rep["inlines"] = _serialize_inlines(self.admin, instance)
        # Resolve each @compact_tree field's root object for this record, so the
        # SPA knows which subtree to fetch (or None to hide the element).
        from theia_ng.introspection.builder import _model_key

        for name, _opts in self.admin.compact_tree_fields():
            root = getattr(self.admin, name)(instance)
            rep[name] = (
                {"key": _model_key(type(root)), "pk": root.pk} if root is not None else None
            )
        return JsonResponse(rep)

    def patch(self, request: HttpRequest, model_key: str, pk: str):
        instance = self._get_object(request, pk)
        if not self.admin.has_change_permission(request, instance):
            return _forbidden()
        data = _json_body(request)
        if data is None:
            return JsonResponse({"detail": "Invalid JSON body"}, status=400)
        before = self.adapter.to_representation(instance)
        try:
            with transaction.atomic():
                instance = self.adapter.save(instance, data, partial=True)
                _save_inlines(self.admin, instance, data)
        except AdapterValidationError as exc:
            return _validation_response(exc)
        except DjangoValidationError as exc:
            return _inline_error_response(exc)
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
            if any(_lookup_spawns_duplicates(target, name) for name in target_admin.search_fields):
                qs = qs.distinct()

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


class TreeFullView(_BaseModelView):
    """The subtree rooted at a record with all descendants assembled eagerly
    (no lazy per-node loading), for the compact hierarchy on the detail page.
    """

    def get(self, request: HttpRequest, model_key: str, pk: str):
        from theia_ng.introspection.tree import build_full_subtree

        try:
            instance = self.admin.get_queryset(request).get(pk=pk)
        except self.model.DoesNotExist:
            raise Http404(f"{self.model._meta.object_name} {pk!r} not found")
        if not self.admin.has_view_permission(request, instance):
            return _forbidden()
        # ?root=self roots at this record (descendants only) for the @compact_tree
        # field; the default climbs to the topmost ancestor for the page section.
        from_root = request.GET.get("root") != "self"
        # ?current=app.model:pk flags a different node as "this record" (a field
        # rooted at an ancestor still highlights the page's actual record).
        current = None
        raw_current = request.GET.get("current")
        if raw_current and ":" in raw_current:
            ckey, cpk = raw_current.rsplit(":", 1)
            current = (ckey, cpk)
        return JsonResponse(
            build_full_subtree(
                self.model, self.admin, instance, request, from_root=from_root, current=current
            )
        )


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
        body = _json_body(request) or {}
        params = body.get("params", {}) or {}
        ids = body.get("ids", []) or []
        # "Select all matching": operate on the whole filtered queryset (the rows
        # the list is showing), reconstructed server-side from the same filters —
        # not a (possibly huge) list of ids.
        select_all = bool(body.get("all"))
        if select_all:
            queryset = apply_list_filters(
                self.admin.get_queryset(request),
                self.model,
                self.admin,
                body.get("filters", {}) or {},
                request,
            )
        else:
            queryset = self.model._default_manager.filter(pk__in=ids)

        # Built-in bulk delete (mirrors django admin's delete_selected).
        if action_key == "delete_selected":
            if not self.admin.list_selectable or not self.admin.has_delete_permission(request):
                return _forbidden()
            count = queryset.count()
            queryset.delete()
            audit.record(
                request,
                "action",
                model_key,
                object_repr=f"delete_selected ({count} objects)",
                changes={"action": "delete_selected", "all": select_all, "count": count},
            )
            return JsonResponse({"detail": "ok", "result": {"deleted": count}})

        if action_key not in self.admin.actions:
            raise Http404(f"Action {action_key!r} is not registered")
        if not self.admin.has_change_permission(request):
            return _forbidden()

        method = getattr(self.admin, action_key, None)
        if not callable(method):
            return JsonResponse({"detail": "Action not implemented"}, status=501)

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

        n = queryset.count() if select_all else len(ids)
        result = method(request, queryset, params) if meta else method(request, queryset)
        audit.record(
            request,
            "action",
            model_key,
            object_repr=f"{action_key} ({n} objects)",
            # `count` is the authoritative object count (it covers the
            # select-all-matching case, where `ids` is empty); `ids` is kept for
            # traceability of an explicit selection.
            changes={
                "action": action_key,
                "all": select_all,
                "count": n,
                "ids": [str(i) for i in ids],
                "params": params,
            },
        )
        return JsonResponse(
            {
                "detail": "ok",
                "result": result if isinstance(result, (dict, list, str, int, float, bool)) else None,
            }
        )
