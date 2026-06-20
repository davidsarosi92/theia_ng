"""IR caching.

The IR is introspected at runtime, but its *structure* (fields, list config,
relations, actions) only changes per deploy — not per request and not per user.
So we cache the structural payload behind a version key and compute the per-user
``perms`` fresh on each request (cheap permission checks).

Version key: ``THEIA_NG['CACHE_VERSION']`` (bump on deploy to invalidate), with
a TTL fallback (``THEIA_NG['SCHEMA_TTL']``, default 300s) so stale structure
self-heals even if ops forget to bump. Set ``SCHEMA_TTL`` to 0 to disable
caching entirely (handy in development).

Uses Django's cache framework; configure a shared backend (e.g. Redis) in
production so all workers share one version, as in the iBar StockCache pattern.
"""

from __future__ import annotations

from typing import Any, Callable

from django.core.cache import cache

import theia_ng
from theia_ng.siteconfig import cache_buster, conf


def _ttl() -> int:
    return int(conf().get("SCHEMA_TTL", 300))


def _version() -> str:
    return str(conf().get("CACHE_VERSION", theia_ng.__version__))


def _key(suffix: str) -> str:
    # `cache_buster` (bumped by the admin "clear cache" action) is folded in so a
    # flush invalidates only Theia's IR keys, without touching CACHE_VERSION.
    return f"theia_ng:ir:v{_version()}.{cache_buster()}:{suffix}"


def cached_structure(suffix: str, builder: Callable[[], Any]) -> Any:
    """Return the cached structural payload for ``suffix`` (or build + store)."""
    ttl = _ttl()
    if ttl <= 0:
        return builder()
    key = _key(suffix)
    value = cache.get(key)
    if value is None:
        value = builder()
        cache.set(key, value, ttl)
    return value
