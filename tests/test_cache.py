"""IR structural caching: hit/miss, version invalidation, disable."""

from django.core.cache import cache

from theia_ng import cache as ircache


def test_cached_structure_builds_once_and_invalidates_on_version(settings):
    cache.clear()
    calls: list[int] = []

    def build() -> dict:
        calls.append(1)
        return {"built": len(calls)}

    settings.THEIA_NG = {"SCHEMA_TTL": 300, "CACHE_VERSION": "a"}
    first = ircache.cached_structure("x", build)
    second = ircache.cached_structure("x", build)
    assert first == second
    assert len(calls) == 1  # second call served from cache

    # Bumping the version invalidates.
    settings.THEIA_NG = {"SCHEMA_TTL": 300, "CACHE_VERSION": "b"}
    ircache.cached_structure("x", build)
    assert len(calls) == 2


def test_ttl_zero_disables_caching(settings):
    cache.clear()
    calls: list[int] = []

    settings.THEIA_NG = {"SCHEMA_TTL": 0}
    ircache.cached_structure("y", lambda: calls.append(1))
    ircache.cached_structure("y", lambda: calls.append(1))
    assert len(calls) == 2  # always rebuilt
