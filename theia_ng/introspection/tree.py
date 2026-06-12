"""Build a parent→children hierarchy for a single record — lazily.

Models opt in via ``ModelAdmin.tree_parent`` (forward FK up to the parent) and
``ModelAdmin.tree_children`` (reverse accessor names down to the children).

The tree is loaded on demand so it scales to thousands of relations:

* ``build_tree`` returns the root node plus the ``path`` (root → opened record).
  Each node carries its *child groups* — one per ``tree_children`` accessor —
  with a **count only**, not the children themselves.
* ``build_children`` returns one child group's records, **searched and
  paginated** (against the child ModelAdmin's ``search_fields`` /
  ``list_per_page``). Each returned child is itself a node (with its own child
  group counts), so the SPA can keep drilling down.

A ``focus`` pk jumps straight to the page containing a given child, so the SPA
can auto-expand the lineage down to the opened record.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.core.paginator import Paginator
from django.db.models import Q

from theia_ng.introspection.builder import SCHEMA_VERSION, _model_key

if TYPE_CHECKING:
    from django.db.models import Model
    from django.http import HttpRequest

    from theia_ng.options import ModelAdmin
    from theia_ng.registry import TheiaSite


def _node_perms(admin: ModelAdmin, request: HttpRequest, obj: Model) -> dict[str, bool]:
    return {
        "view": admin.has_view_permission(request, obj),
        "change": admin.has_change_permission(request, obj),
        "delete": admin.has_delete_permission(request, obj),
    }


def _child_models(model: type[Model]) -> dict[str, type[Model]]:
    """Reverse-relation accessor name → related model, for resolving children."""
    return {rel.get_accessor_name(): rel.related_model for rel in model._meta.related_objects}


def _resolve_child_admin(
    model: type[Model], accessor: str, site: TheiaSite
) -> tuple[type[Model], ModelAdmin] | None:
    """(child_model, child_admin) for a ``tree_children`` accessor, if registered."""
    related = _child_models(model).get(accessor)
    if related is None:
        return None
    return site.get_model(_model_key(related))


def _child_groups(
    model: type[Model], admin: ModelAdmin, obj: Model, request: HttpRequest, site: TheiaSite
) -> list[dict[str, Any]]:
    """One descriptor per child relation: target + label + count (no records)."""
    groups: list[dict[str, Any]] = []
    for accessor in admin.tree_children:
        resolved = _resolve_child_admin(model, accessor, site)
        if resolved is None:
            continue  # accessor isn't a reverse relation, or the child isn't registered
        child_model, child_admin = resolved
        if not child_admin.has_view_permission(request):
            continue
        manager = getattr(obj, accessor, None)
        if manager is None:
            continue
        groups.append({
            "accessor": accessor,
            "key": _model_key(child_model),
            "label": str(child_model._meta.verbose_name_plural),
            "count": manager.count(),
            "searchable": bool(child_admin.search_fields),
        })
    return groups


def _node(
    model: type[Model],
    admin: ModelAdmin,
    obj: Model,
    request: HttpRequest,
    site: TheiaSite,
    current: tuple[str, str],
) -> dict[str, Any]:
    return {
        "key": _model_key(model),
        "model_label": str(model._meta.verbose_name),
        "pk": obj.pk,
        "label": admin.display(obj),
        "perms": _node_perms(admin, request, obj),
        "is_current": (_model_key(model), str(obj.pk)) == current,
        "child_groups": _child_groups(model, admin, obj, request, site),
    }


def _resolve_lineage(
    model: type[Model], admin: ModelAdmin, obj: Model, site: TheiaSite
) -> list[tuple[type[Model], ModelAdmin, Model]]:
    """The chain from the topmost ancestor down to ``obj`` (root first)."""
    chain = [(model, admin, obj)]
    cur_model, cur_admin, cur_obj = model, admin, obj
    seen: set[tuple[type[Model], Any]] = set()
    while cur_admin.tree_parent:
        if (cur_model, cur_obj.pk) in seen:  # cycle guard
            break
        seen.add((cur_model, cur_obj.pk))
        parent = getattr(cur_obj, cur_admin.tree_parent, None)
        if parent is None:
            break
        resolved = site.get_model(_model_key(type(parent)))
        if resolved is None:
            break  # parent model not registered — stop here, this is the root
        cur_model, cur_admin = resolved
        cur_obj = parent
        chain.append((cur_model, cur_admin, cur_obj))
    chain.reverse()
    return chain


def build_tree(
    model: type[Model], admin: ModelAdmin, obj: Model, request: HttpRequest
) -> dict[str, Any]:
    """Root node + the lineage path (root → opened record). Children load lazily."""
    from theia_ng.registry import site

    chain = _resolve_lineage(model, admin, obj, site)
    current = (_model_key(model), str(obj.pk))
    root_model, root_admin, root_obj = chain[0]
    return {
        "schema_version": SCHEMA_VERSION,
        "root": _node(root_model, root_admin, root_obj, request, site, current),
        "path": [{"key": _model_key(m), "pk": o.pk} for (m, _a, o) in chain],
        "current": {"key": current[0], "pk": obj.pk},
    }


class ChildAccessDenied(Exception):
    """The child model exists but the user may not view it."""


def build_children(
    parent_model: type[Model],
    parent_admin: ModelAdmin,
    parent_obj: Model,
    accessor: str,
    request: HttpRequest,
    *,
    page: int = 1,
    search: str = "",
    focus: str | None = None,
) -> dict[str, Any]:
    """One child group's records — searched (``search_fields``) and paginated.

    ``focus`` jumps to the page holding that child pk (ignored when searching).
    Raises ``LookupError`` for an unknown/unregistered accessor and
    ``ChildAccessDenied`` when the child model isn't viewable.
    """
    from theia_ng.registry import site

    resolved = _resolve_child_admin(parent_model, accessor, site)
    if resolved is None:
        raise LookupError(accessor)
    child_model, child_admin = resolved
    if not child_admin.has_view_permission(request):
        raise ChildAccessDenied(accessor)

    qs = getattr(parent_obj, accessor).all()
    if search and child_admin.search_fields:
        q = Q()
        for name in child_admin.search_fields:
            q |= Q(**{f"{name}__icontains": search})
        qs = qs.filter(q)
    qs = qs.order_by("pk")

    per_page = child_admin.list_per_page
    paginator = Paginator(qs, per_page)
    if focus not in (None, "") and not search:
        # Jump to the page containing `focus` (pk-ordered): its 1-based position
        # is the count of rows with pk <= focus.
        try:
            position = qs.filter(pk__lte=focus).count()
            if position:
                page = (position + per_page - 1) // per_page
        except (ValueError, TypeError):
            pass

    current = (_model_key(child_model), "")  # children list never flags "current"
    page_obj = paginator.get_page(page)
    results = [
        _node(child_model, child_admin, obj, request, site, current) for obj in page_obj
    ]
    return {
        "key": _model_key(child_model),
        "accessor": accessor,
        "count": paginator.count,
        "page": page_obj.number,
        "num_pages": paginator.num_pages,
        "results": results,
    }
