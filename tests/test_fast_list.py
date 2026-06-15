"""Fast list path — eligibility + byte-identical output.

The strongest correctness guarantee: for fast-eligible models, the fast batch
serializer must produce rows identical to the generic per-instance serializer.
We register models whose labels are all DB-expressible (``display_field`` set on
every relevant admin), point ``FAST_LIST_PROVIDER`` at fastberry's provider, and
diff its output against ``serialize_list_row`` for the same rows. We also assert
ineligible admins are not planned and that the fast path issues no per-row
queries.

theia core does not depend on fastberry; this test exercises the integration via
the configured provider, so it is skipped if fastberry is not installed.
"""

from decimal import Decimal

import pytest

pytest.importorskip("fastberry.list_provider")  # provider is an optional test dep

from django.db import connection, models  # noqa: E402
from django.test.utils import CaptureQueriesContext  # noqa: E402

import theia_ng  # noqa: E402
from theia_ng.adapters import resolve_adapter  # noqa: E402
from theia_ng.adapters.fast import FastRestAdapter  # noqa: E402
from theia_ng.api import fast_list  # noqa: E402
from theia_ng.api.serialization import serialize_list_row  # noqa: E402
from theia_ng.registry import site  # noqa: E402

PROVIDER = "fastberry.list_provider.ListProvider"

# Use the installed sampleapp label so Django's relation machinery (auto M2M
# through model) resolves correctly; tables are created/dropped per test.
APP = "sampleapp"


class FCategory(models.Model):
    title = models.CharField(max_length=100)

    class Meta:
        app_label = APP

    def __str__(self):  # NOT used by the fast path (display_field wins)
        return f"cat:{self.title}"


class FTag(models.Model):
    title = models.CharField(max_length=100)

    class Meta:
        app_label = APP


class FStock(models.Model):
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)
    category = models.ForeignKey(FCategory, null=True, on_delete=models.SET_NULL)
    tags = models.ManyToManyField(FTag)

    class Meta:
        app_label = APP


@pytest.fixture
def registered(transactional_db, settings):
    # Wire the host-configured provider (theia core has no fastberry dependency).
    settings.THEIA_NG = {**(getattr(settings, "THEIA_NG", {}) or {}), "LIST_PROVIDER": PROVIDER}
    fast_list.reset_caches()
    # transactional_db (not the atomic `db` fixture) so the SQLite schema editor
    # can run DDL; tables are dropped again in teardown.
    existing = set(connection.introspection.table_names())
    for m in (FStock, FTag, FCategory):  # reverse dep order, drop leftovers first
        if m._meta.db_table in existing:
            with connection.schema_editor() as se:
                se.delete_model(m)
    for m in (FCategory, FTag, FStock):
        with connection.schema_editor() as se:
            se.create_model(m)

    class FCategoryAdmin(theia_ng.ModelAdmin):
        list_display = ["title"]
        display_field = "title"

    class FTagAdmin(theia_ng.ModelAdmin):
        list_display = ["title"]
        display_field = "title"

    class FStockAdmin(theia_ng.ModelAdmin):
        list_display = ["name", "category", "tags", "price", "is_active"]
        display_field = "name"

    for m, admin_cls in ((FCategory, FCategoryAdmin), (FTag, FTagAdmin), (FStock, FStockAdmin)):
        if site.is_registered(m):
            site.unregister(m)
        site.register(m, admin_cls)

    c1 = FCategory.objects.create(title="Beers")
    t1 = FTag.objects.create(title="red")
    t2 = FTag.objects.create(title="new")

    s1 = FStock.objects.create(name="A", price=Decimal("9.99"), is_active=True, category=c1)
    s1.tags.set([t1, t2])
    FStock.objects.create(name="B", price=Decimal("1.50"), is_active=False, category=None)

    fast_list._CACHE.clear()
    yield
    for m in (FStock, FTag, FCategory):
        site.unregister(m)
        with connection.schema_editor() as se:
            se.delete_model(m)
    fast_list._CACHE.clear()


def _generic_rows(model, admin):
    return [
        serialize_list_row(obj, model, admin, admin.list_display)
        for obj in model.objects.order_by("pk")
    ]


def test_stock_is_fast_eligible_and_uses_fast_adapter(registered):
    _model, admin = site.get_model(f"{APP}.fstock")
    assert fast_list.build_fast_schema(FStock, admin) is not None
    assert isinstance(resolve_adapter(FStock, admin), FastRestAdapter)


def test_fast_output_matches_generic(registered):
    _model, admin = site.get_model(f"{APP}.fstock")
    fls = fast_list.build_fast_schema(FStock, admin)

    fast_rows = fast_list.serialize_page(fls, FStock.objects.order_by("pk"))
    generic_rows = _generic_rows(FStock, admin)

    # Same rows, same keys, same values — byte-identical contract.
    assert fast_rows == generic_rows
    # spot-checks on the shape we care about
    by_name = {r["name"]: r for r in fast_rows}
    assert by_name["A"]["category"] == {"id": 1, "label": "Beers"}
    assert by_name["B"]["category"] is None
    assert by_name["A"]["price"] == "9.99"
    assert {t["label"] for t in by_name["A"]["tags"]} == {"red", "new"}
    assert by_name["B"]["tags"] == []
    assert by_name["A"]["__str__"] == "A"
    assert by_name["A"]["pk"] == by_name["A"]["id"]


def test_fast_path_no_per_row_queries(registered):
    from django.conf import settings as dj_settings

    _model, admin = site.get_model(f"{APP}.fstock")
    fls = fast_list.build_fast_schema(FStock, admin)
    # add more rows to prove query count is independent of row count
    extra = FCategory.objects.first()
    for i in range(10):
        FStock.objects.create(name=f"x{i}", price=Decimal("1.00"), category=extra)

    dj_settings.DEBUG = True
    try:
        with CaptureQueriesContext(connection) as ctx:
            fast_list.serialize_page(fls, FStock.objects.order_by("pk"))
        # 1 query for the stock rows (+ FK label joins) + 1 for the m2m through.
        assert len(ctx.captured_queries) == 2, [q["sql"] for q in ctx.captured_queries]
    finally:
        dj_settings.DEBUG = False


def test_ineligible_admins_have_no_plan():
    # build_plan is provider-independent, so it isolates the eligibility logic.

    # display_field missing -> not eligible
    class NoDisplay(theia_ng.ModelAdmin):
        list_display = ["name"]

    assert fast_list.build_plan(FStock, NoDisplay(FStock, site)) is None

    # computed column -> not eligible
    class Computed(theia_ng.ModelAdmin):
        list_display = ["name", "blurb"]
        display_field = "name"

        @theia_ng.display(description="Blurb")
        def blurb(self, obj):
            return obj.name.upper()

    assert fast_list.build_plan(FStock, Computed(FStock, site)) is None

    # relation-spanning column -> not eligible
    class Spanning(theia_ng.ModelAdmin):
        list_display = ["name", "category__title"]
        display_field = "name"

    assert fast_list.build_plan(FStock, Spanning(FStock, site)) is None


def test_no_provider_means_no_fast_path(registered, settings):
    # With LIST_PROVIDER unset, eligible models still get no fast adapter.
    settings.THEIA_NG = {k: v for k, v in (settings.THEIA_NG or {}).items() if k != "LIST_PROVIDER"}
    fast_list.reset_caches()
    _model, admin = site.get_model(f"{APP}.fstock")
    assert fast_list.build_plan(FStock, admin) is not None  # still eligible
    assert fast_list.build_fast_schema(FStock, admin) is None  # but no provider -> no fast path
