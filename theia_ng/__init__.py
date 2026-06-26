"""Theia NG — a dynamic Angular admin for Django, generated from your models."""

from theia_ng.actions import ActionField, action
from theia_ng.filters import ListFilter
from theia_ng.options import Inline, ModelAdmin, compact_tree, display
from theia_ng.registry import site

__all__ = [
    "site",
    "ModelAdmin",
    "Inline",
    "display",
    "compact_tree",
    "ListFilter",
    "action",
    "ActionField",
    "register",
]

# Track the installed distribution version (single source of truth: pyproject).
# A hardcoded value drifts — and ``cache.py`` uses ``__version__`` as the default
# IR-cache version, so a stale value would freeze cache invalidation across
# upgrades.
try:
    from importlib.metadata import PackageNotFoundError, version as _version

    __version__ = _version("theia_ng")
    del _version, PackageNotFoundError
except Exception:  # source checkout without install metadata
    __version__ = "0.0.0+dev"

# Convenience: `from theia_ng import register`
register = site.register

default_app_config = "theia_ng.apps.TheiaNgConfig"
