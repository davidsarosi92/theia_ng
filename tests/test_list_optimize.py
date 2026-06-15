"""Auto select_related for list rows — path derivation + N+1 elimination.

Exercises the three sources the optimizer reads: the row's own ``__str__``, a
computed ``@display`` column, and a concrete FK whose target ``__str__`` reaches
across a relation. Asserts the derived paths and that the list query count is
flat with row count (no N+1) — and that it falls back cleanly when disabled.
"""

import pytest
from django.db import connection, models
from django.test.utils import CaptureQueriesContext

import theia_ng
from theia_ng.api import list_optimize
from theia_ng.api.list_optimize import select_related_paths
from theia_ng.api.serialization import serialize_list_row
from theia_ng.registry import site

APP = "sampleapp"


class LoCountry(models.Model):
    name = models.CharField(max_length=100)

    class Meta:
        app_label = APP

    def __str__(self):
        return self.name


class LoCity(models.Model):
    name = models.CharField(max_length=100)
    country = models.ForeignKey(LoCountry, on_delete=models.CASCADE)

    class Meta:
        app_label = APP

    def __str__(self):
        return f"{self.name}, {self.country.name}"  # traverses country


class LoShop(models.Model):
    title = models.CharField(max_length=100)
    city = models.ForeignKey(LoCity, null=True, on_delete=models.SET_NULL)

    class Meta:
        app_label = APP

    def __str__(self):
        return f"{self.title} @ {self.city.name}"  # traverses city (depth 1)


@pytest.fixture
def shops(transactional_db):
    existing = set(connection.introspection.table_names())
    for m in (LoShop, LoCity, LoCountry):
        if m._meta.db_table in existing:
            with connection.schema_editor() as se:
                se.delete_model(m)
    for m in (LoCountry, LoCity, LoShop):
        with connection.schema_editor() as se:
            se.create_model(m)

    class LoShopAdmin(theia_ng.ModelAdmin):
        list_display = ["title", "region"]

        @theia_ng.display(description="Region")
        def region(self, obj):
            return obj.city.country.name  # traverses city.country

    for m in (LoShop,):
        if site.is_registered(m):
            site.unregister(m)
    site.register(LoShop, LoShopAdmin)

    hu = LoCountry.objects.create(name="HU")
    de = LoCountry.objects.create(name="DE")
    bp = LoCity.objects.create(name="Budapest", country=hu)
    muc = LoCity.objects.create(name="Munich", country=de)
    for i in range(10):
        LoShop.objects.create(title=f"S{i}", city=bp if i % 2 else muc)

    list_optimize.reset_cache()
    yield
    site.unregister(LoShop)
    for m in (LoShop, LoCity, LoCountry):
        with connection.schema_editor() as se:
            se.delete_model(m)
    list_optimize.reset_cache()


def test_derived_paths(shops):
    _m, admin = site.get_model(f"{APP}.loshop")
    paths = select_related_paths(LoShop, admin)
    # city.country comes from the @display column AND the LoCity.__str__ label;
    # 'city' from LoShop.__str__. 'city__country' implies 'city' for select_related.
    assert "city__country" in paths


def _serialize(admin):
    rows = []
    from theia_ng.api.crud_views import _apply_list_display
    from theia_ng.api.serialization import relation_field_names, serializable_fields
    fk, _ = relation_field_names(serializable_fields(LoShop))
    related = list(dict.fromkeys([*fk, *select_related_paths(LoShop, admin), *admin.list_select_related]))
    for obj in LoShop.objects.select_related(*related):
        rep = serialize_list_row(obj, LoShop, admin, admin.list_display)
        _apply_list_display(admin, obj, rep)
        rows.append(rep)
    return rows


def test_no_n_plus_one(shops):
    from django.conf import settings as dj
    _m, admin = site.get_model(f"{APP}.loshop")
    dj.DEBUG = True
    try:
        with CaptureQueriesContext(connection) as ctx:
            rows = _serialize(admin)
        assert len(rows) == 10
        # one query for the whole page; flat regardless of row count
        assert len(ctx.captured_queries) == 1, [q["sql"] for q in ctx.captured_queries]
        # labels still correct
        assert rows[0]["region"] in ("HU", "DE")
    finally:
        dj.DEBUG = False


def test_disabled_setting_returns_no_paths(shops, settings):
    settings.THEIA_NG = {**(settings.THEIA_NG or {}), "AUTO_SELECT_RELATED": False}
    list_optimize.reset_cache()
    _m, admin = site.get_model(f"{APP}.loshop")
    assert select_related_paths(LoShop, admin) == ()
