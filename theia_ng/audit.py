"""Write-side audit logging for Theia NG.

``record`` persists one ``LogEntry`` per create / update / delete / action. It is
best-effort: any failure here is swallowed so auditing never breaks the actual
operation. ``diff`` computes the field-level change set from two serialized
representations (the adapter's ``to_representation`` before/after a save).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from django.http import HttpRequest

# Audit-noise fields excluded from the diff (they change on every write).
_DIFF_EXCLUDE = {"pk", "modified", "modified_by"}


def diff(before: dict[str, Any], after: dict[str, Any]) -> dict[str, list[Any]]:
    """``{field: [old, new]}`` for keys whose value changed.

    On create, pass ``before={}`` — every set field shows as ``[None, new]``.
    """
    changes: dict[str, list[Any]] = {}
    for key in after:
        if key in _DIFF_EXCLUDE:
            continue
        old = before.get(key)
        new = after[key]
        if old != new:
            changes[key] = [old, new]
    return changes


def record(
    request: HttpRequest,
    action: str,
    model_key: str,
    *,
    object_pk: Any = "",
    object_repr: str = "",
    changes: dict | None = None,
) -> None:
    """Persist one audit entry. Never raises."""
    try:
        from theia_ng.models import LogEntry

        user = getattr(request, "user", None)
        user = user if (user and user.is_authenticated) else None
        LogEntry.objects.create(
            user=user,
            username=(user.get_username() if user else ""),
            action=action,
            model_key=model_key,
            object_pk=str(object_pk or ""),
            object_repr=(object_repr or "")[:255],
            changes=changes or {},
        )
    except Exception:
        # Auditing must never break the operation it records.
        pass
