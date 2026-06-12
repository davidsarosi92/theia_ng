"""Theia NG's own registrations (autodiscovered like any app's ``theia.py``).

Registers the built-in MenuView model so admins can create/edit sidebar views
through the same admin UI.
"""

import theia_ng
from theia_ng.models import MenuView


@theia_ng.register(MenuView)
class MenuViewAdmin(theia_ng.ModelAdmin):
    list_display = ["name", "position"]
    ordering = ["position", "name"]
    search_fields = ["name"]
    # The "Models" field picks from the registered models (multiselect).
    registry_choice_fields = ["model_keys"]
    # "Fields per model" picks, for each chosen model, which fields the view shows.
    model_field_select = {"model_fields": "model_keys"}
