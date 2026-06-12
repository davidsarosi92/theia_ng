"""Parameterized custom actions.

A plain action is a ModelAdmin method named in ``actions`` that runs over a
selection: ``method(request, queryset)``.

A *parameterized* action additionally collects a small form from the user (a
message body, a flag, a relation picker, …). Declare it with ``@theia_ng.action``
and it receives the collected values as a third ``params`` dict::

    @theia_ng.action(
        label="Broadcast message",
        selection="none",                       # ignores row selection
        fields=[
            theia_ng.ActionField("body", "text", label="Message", required=True),
            theia_ng.ActionField("send_push", "boolean", label="Send push"),
            theia_ng.ActionField("recipients", "m2m", relation="users.customuser"),
        ],
    )
    def broadcast(self, request, queryset, params):
        ...

``selection`` controls whether the action needs selected rows:
``"required"`` (default for plain actions), ``"optional"``, or ``"none"``.
"""

from __future__ import annotations

from typing import Any, Callable

# Action field types reuse the IR's closed type set (see introspection.types).
# Relation types ("fk"/"m2m") also take ``relation="app.model"``.


class ActionField:
    """One input in an action's form. ``type`` is an IR FieldType value."""

    def __init__(
        self,
        name: str,
        type: str,
        *,
        label: str | None = None,
        required: bool = False,
        default: Any = None,
        help_text: str = "",
        choices: list[tuple[Any, str]] | None = None,
        relation: str | None = None,
        widget: str | None = None,
    ) -> None:
        self.name = name
        self.type = type
        self.label = label or name.replace("_", " ").capitalize()
        self.required = required
        self.default = default
        self.help_text = help_text
        self.choices = choices
        self.relation = relation  # target model key for fk/m2m
        self.widget = widget


def action(
    label: str | None = None,
    *,
    fields: list[ActionField] | None = None,
    selection: str = "required",
) -> Callable:
    """Mark a ModelAdmin method as a parameterized action.

    Decorated actions are called ``method(request, queryset, params)`` (plain,
    undecorated actions stay ``method(request, queryset)``).
    """

    def decorator(func: Callable) -> Callable:
        func._theia_action = {  # type: ignore[attr-defined]
            "label": label or func.__name__.replace("_", " ").capitalize(),
            "fields": list(fields or []),
            "selection": selection,
        }
        return func

    return decorator
