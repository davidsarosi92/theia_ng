"""Searching across a to-many relation must not duplicate rows.

A ``search_fields`` (or ``list_filter``) lookup that spans a reverse FK / M2M
joins the related table, so an object with N matching related rows would appear
N times. ``apply_list_filters`` collapses these with ``.distinct()`` — mirroring
Django admin — so each object is listed once (the "user shown once per
registration" bug)."""

from types import SimpleNamespace

import pytest

from theia_ng.api.crud_views import _lookup_spawns_duplicates, apply_list_filters
from tests.testproject.sampleapp.models import House, Space


def test_lookup_spawns_duplicates_only_for_to_many():
    # Reverse FK (House -> spaces) is multi-valued -> joining duplicates rows.
    assert _lookup_spawns_duplicates(House, "spaces__name") is True
    # A local field and a forward FK (to-one) never duplicate.
    assert _lookup_spawns_duplicates(House, "name") is False
    assert _lookup_spawns_duplicates(Space, "house__name") is False


@pytest.mark.django_db
def test_search_across_to_many_relation_is_deduplicated():
    alpha = House.objects.create(name="Alpha")
    Space.objects.create(name="bar one", house=alpha)
    Space.objects.create(name="bar two", house=alpha)  # 2nd match for the same house
    beta = House.objects.create(name="Beta")
    Space.objects.create(name="lounge", house=beta)

    admin = SimpleNamespace(search_fields=["spaces__name"], list_filter=[])
    qs = apply_list_filters(House.objects.all(), House, admin, {"search": "bar"}, None)

    # Without .distinct() the join would yield Alpha twice.
    assert [h.name for h in qs] == ["Alpha"]
    assert qs.count() == 1
