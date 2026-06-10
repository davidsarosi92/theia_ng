"""Theia NG — a dynamic Angular admin for Django, generated from your models."""

from theia_ng.options import ModelAdmin
from theia_ng.registry import site

__all__ = ["site", "ModelAdmin", "register"]

__version__ = "0.0.1"

# Convenience: `from theia_ng import register`
register = site.register

default_app_config = "theia_ng.apps.TheiaNgConfig"
