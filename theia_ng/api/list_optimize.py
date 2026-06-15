"""Automatic ``select_related`` for list rows.

A list row renders every concrete forward FK as a ``{id, label}`` cell (the label
is the target admin's ``display()`` — i.e. its ``display_field`` or ``__str__``),
plus the row's own ``__str__`` label and any computed ``@display`` columns. When
those labels reach *across* relations, the list would issue a per-row query for
each hop (an N+1). This module derives, once per model, the forward-relation
paths those labels traverse, so the list view can ``select_related`` them.

The output is unchanged — this only collapses the per-row queries into joins.

Bounded and safe by construction:

- only concrete **forward** FK / O2O segments are followed (never reverse or
  M2M, which ``select_related`` cannot do — those simply stop a path);
- paths come from the literal attribute chains found in the relevant
  ``__str__`` / ``@display`` sources, so each path is finite; there is no
  recursion beyond one level into each FK target's ``__str__``;
- anything unparseable (C ``__str__``, lambdas) is skipped.

Disable with ``THEIA_NG['AUTO_SELECT_RELATED'] = False``.
"""

from __future__ import annotations

import ast
import inspect
import textwrap
from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.core.exceptions import FieldDoesNotExist
from django.db import models

from theia_ng.registry import site

if TYPE_CHECKING:
    from theia_ng.options import ModelAdmin

# model class -> tuple of select_related paths (cached; admins are singletons).
_CACHE: dict[type, tuple[str, ...]] = {}


def reset_cache() -> None:
    """Clear the per-model path cache (tests / dynamic re-registration)."""
    _CACHE.clear()


def _enabled() -> bool:
    conf = getattr(settings, "THEIA_NG", {}) or {}
    return bool(conf.get("AUTO_SELECT_RELATED", True))


def _attr_chains(source: str, roots: set[str]) -> list[list[str]]:
    """Attribute-access chains (lists of attr names) rooted at a Name in ``roots``.

    e.g. ``self.house.company.registration`` -> ``["house", "company", "registration"]``.
    """
    try:
        tree = ast.parse(textwrap.dedent(source))
    except (SyntaxError, ValueError):
        return []
    chains: list[list[str]] = []

    class _V(ast.NodeVisitor):
        def visit_Attribute(self, node: ast.Attribute) -> None:
            parts: list[str] = []
            cur: ast.expr = node
            while isinstance(cur, ast.Attribute):
                parts.append(cur.attr)
                cur = cur.value
            if isinstance(cur, ast.Name) and cur.id in roots:
                chains.append(list(reversed(parts)))
            self.generic_visit(node)

    _V().visit(tree)
    return chains


def _forward_path(model: type[models.Model], chain: list[str]) -> str | None:
    """Map an attribute chain to a forward-relation path on ``model``.

    Follows concrete forward FK / O2O segments only, stopping at the first scalar
    (or reverse / M2M) attribute. Returns the dotted path, or None if it follows
    no relation.
    """
    m = model
    segs: list[str] = []
    for attr in chain:
        try:
            f = m._meta.get_field(attr)
        except (FieldDoesNotExist, AttributeError):
            break
        if (f.many_to_one or f.one_to_one) and getattr(f, "concrete", False):
            segs.append(attr)
            m = f.related_model
        else:
            break
    return "__".join(segs) if segs else None


def _source(func: Any) -> str | None:
    try:
        return inspect.getsource(func)
    except (OSError, TypeError):
        return None


def _scalar_display_field(model: type[models.Model], admin: Any) -> str | None:
    df = getattr(admin, "display_field", None)
    if not df:
        return None
    try:
        f = model._meta.get_field(df)
    except FieldDoesNotExist:
        return None
    return df if (getattr(f, "concrete", False) and not f.is_relation) else None


def _paths_from_str(model: type[models.Model], admin_for_model: Any | None) -> set[str]:
    """Forward paths the model's label traverses.

    If the (registered) admin has a scalar ``display_field`` the label is a column
    (no traversal); otherwise it is ``model.__str__``.
    """
    if admin_for_model is not None and _scalar_display_field(model, admin_for_model):
        return set()
    dunder = model.__dict__.get("__str__")
    src = _source(dunder) if dunder is not None else None
    if not src:
        return set()
    paths = {_forward_path(model, c) for c in _attr_chains(src, {"self"})}
    return {p for p in paths if p}


def select_related_paths(model: type[models.Model], admin: ModelAdmin) -> tuple[str, ...]:
    """Forward-relation paths the list-row serialization for ``model`` traverses.

    Cached per model. Empty when disabled."""
    if not _enabled():
        return ()
    if model in _CACHE:
        return _CACHE[model]

    paths: set[str] = set()

    # 1) the row's own label (admin.display -> display_field or model.__str__)
    paths |= _paths_from_str(model, admin)

    # 2) computed @display columns in list_display
    for name in getattr(admin, "list_display", []) or []:
        meth = getattr(admin, name, None)
        if callable(meth):
            src = _source(meth)
            if not src:
                continue
            try:
                params = list(inspect.signature(meth).parameters)
            except (ValueError, TypeError):
                params = []
            obj_param = params[1] if len(params) > 1 else "obj"
            for chain in _attr_chains(src, {obj_param}):
                p = _forward_path(model, chain)
                if p:
                    paths.add(p)

    # 3) every concrete forward FK is rendered as a {id, label} cell; its label is
    #    the target admin's display() (display_field scalar -> no hop) else the
    #    target's __str__. One level into the target is enough (the label is a
    #    plain string, not a further-serialized row).
    for f in model._meta.concrete_fields:
        if f.many_to_one or f.one_to_one:
            target = f.related_model
            r = site.get_model(f"{target._meta.app_label}.{target._meta.model_name}")
            target_admin = r[1] if r is not None else None
            for tp in _paths_from_str(target, target_admin):
                paths.add(f"{f.name}__{tp}")

    result = tuple(sorted(paths))
    _CACHE[model] = result
    return result
