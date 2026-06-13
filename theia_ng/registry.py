"""The Theia NG site registry — our own, not django.contrib.admin's.

Holds the mapping of registered models to their ModelAdmin-equivalent configs,
and owns the site-level settings (title, mount prefix). One default instance is
exported as ``site``; multiple instances can be mounted under different prefixes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from theia_ng.options import ModelAdmin

if TYPE_CHECKING:
    from django.db.models import Model


class AlreadyRegistered(Exception):
    pass


class NotRegistered(Exception):
    pass


class TheiaSite:
    def __init__(self, name: str = "theia") -> None:
        self.name = name
        self._site_title = "Theia NG Admin"
        self._registry: dict[type[Model], ModelAdmin] = {}

    @property
    def site_title(self) -> str:
        """Top-bar title. ``THEIA_NG['SITE_TITLE']`` (deploy config) wins over a
        programmatic default, so the same source feeds the registry payload and
        the SPA's injected config — no more two-source mismatch."""
        from django.conf import settings

        conf = getattr(settings, "THEIA_NG", {}) or {}
        return conf.get("SITE_TITLE") or self._site_title

    @site_title.setter
    def site_title(self, value: str) -> None:
        self._site_title = value

    def register(self, model: type[Model], admin_class: type[ModelAdmin] | None = None):
        """Register ``model``. Usable as a decorator or a direct call.

        Mirrors django admin ergonomics::

            @site.register(Stock)
            class StockAdmin(ModelAdmin): ...

            # or
            site.register(Stock, StockAdmin)
        """
        def _register(cls: type[ModelAdmin]) -> type[ModelAdmin]:
            if model in self._registry:
                raise AlreadyRegistered(f"{model.__name__} is already registered")
            self._registry[model] = cls(model, self)
            return cls

        if admin_class is not None:
            _register(admin_class)
            return admin_class

        # Bare @register(Model) with no class -> use the default ModelAdmin,
        # but still support decorator form when a class follows.
        def decorator(cls: type[ModelAdmin]) -> type[ModelAdmin]:
            return _register(cls)

        return decorator

    def unregister(self, model: type[Model]) -> None:
        if model not in self._registry:
            raise NotRegistered(f"{model.__name__} is not registered")
        del self._registry[model]

    def is_registered(self, model: type[Model]) -> bool:
        return model in self._registry

    def get_model(self, key: str) -> tuple[type[Model], ModelAdmin] | None:
        """Resolve an ``app_label.model_name`` key to its (model, admin) pair."""
        for model, admin in self._registry.items():
            opts = model._meta
            if f"{opts.app_label}.{opts.model_name}" == key:
                return model, admin
        return None

    @property
    def registry(self) -> dict[type[Model], ModelAdmin]:
        return dict(self._registry)


# The default site instance.
site = TheiaSite()
