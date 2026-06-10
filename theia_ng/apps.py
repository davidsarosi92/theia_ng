from django.apps import AppConfig


class TheiaNgConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "theia_ng"
    verbose_name = "Theia NG Admin"

    def ready(self) -> None:
        # Autodiscover `theia.py` modules across installed apps, mirroring the
        # django.contrib.admin autodiscover pattern (but using OUR registry).
        from django.utils.module_loading import autodiscover_modules

        from theia_ng.registry import site

        autodiscover_modules("theia", register_to=site)
