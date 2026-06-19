"""Discovery translation of django-admin fieldsets / list_editable / inlines."""

from types import SimpleNamespace

from theia_ng.discovery import _translate_inlines, translate_admin
from tests.testproject.sampleapp.models import Bundle, Stock


def _dj(**attrs):
    """A stand-in for a django ModelAdmin (attribute bag) for translate_admin."""
    return SimpleNamespace(**attrs)


def test_translate_list_editable_subset_of_display():
    attrs = translate_admin(Bundle, _dj(list_display=("name", "id"), list_editable=("name", "id")))
    # `id` is auto/non-real-editable but is a real field; both are in display.
    assert attrs["list_editable"] == ["name", "id"]


def test_list_editable_dropped_when_not_in_display():
    attrs = translate_admin(Bundle, _dj(list_display=("id",), list_editable=("name",)))
    assert "list_editable" not in attrs


def test_translate_fieldsets_keeps_real_field_sections():
    fieldsets = [
        (None, {"fields": ["name"]}),
        ("Sec", {"fields": ["name"], "classes": ["collapse"], "description": "d"}),
        ("Bad", {"fields": ["not_a_field"]}),  # dropped (references a non-field)
    ]
    attrs = translate_admin(Bundle, _dj(fieldsets=fieldsets))
    out = attrs["fieldsets"]
    assert [name for name, _ in out] == [None, "Sec"]
    assert out[1][1]["classes"] == ["collapse"]


def test_translate_inlines_maps_to_theia_inline():
    dj_inline = SimpleNamespace(
        model=Stock,
        fk_name="category",
        fields=("name", "quantity"),
        readonly_fields=(),
        exclude=(),
        raw_id_fields=(),
        extra=2,
        can_delete=False,
        template="admin/edit_inline/stacked.html",
    )
    inlines = _translate_inlines([dj_inline])
    assert len(inlines) == 1
    inline = inlines[0]()
    assert inline.model is Stock
    assert inline.fk_name == "category"
    assert inline.fields == ["name", "quantity"]
    assert inline.extra == 2
    assert inline.can_delete is False
    assert inline.style == "stacked"


def test_translate_inlines_defaults_to_tabular():
    dj_inline = SimpleNamespace(model=Stock, template="admin/edit_inline/tabular.html")
    inline = _translate_inlines([dj_inline])[0]()
    assert inline.style == "tabular"
