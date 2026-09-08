"""Theia NG's own registrations (autodiscovered like any app's ``theia.py``).

Registers the built-in MenuView model so admins can create/edit sidebar views
through the same admin UI.
"""

import theia_ng
from theia_ng.models import AssistExample, AssistHint, MenuView


@theia_ng.register(MenuView)
class MenuViewAdmin(theia_ng.ModelAdmin):
    list_display = ["name", "position"]
    ordering = ["position", "name"]
    search_fields = ["name"]
    # The "Models" field picks from the registered models (multiselect).
    registry_choice_fields = ["model_keys"]
    # "Fields per model" picks, for each chosen model, which fields the view shows.
    model_field_select = {"model_fields": "model_keys"}


@theia_ng.register(AssistHint)
class AssistHintAdmin(theia_ng.ModelAdmin):
    description = (
        "Editable help for the natural-language assistant. Ships empty on purpose: "
        "on a local 7B model, added prompt prose made the assistant WORSE on unseen "
        "sentences (82% -> 73%, and 59% when the hint listed trigger words). Write "
        "short descriptions of what a field means; never list trigger words. "
        "Measure any change with Assistant examples before trusting it."
    )
    list_display = ["kind", "model_key", "field_name", "term", "enabled"]
    list_filter = ["kind", "enabled"]
    search_fields = ["model_key", "field_name", "term", "text"]
    ordering = ["model_key", "kind"]
    registry_choice_fields = []
    # The assistant must never be steered by itself.
    assist = False


@theia_ng.register(AssistExample)
class AssistExampleAdmin(theia_ng.ModelAdmin):
    description = (
        "Worked examples: a sentence and the list state it should produce. Doubles "
        "as the regression set — replay these after changing a hint, model or "
        "provider to see whether the change helped or hurt. Turn on 'in prompt' to "
        "also use one as a few-shot example."
    )
    list_display = ["model_key", "prompt", "in_prompt", "enabled"]
    list_filter = ["in_prompt", "enabled"]
    search_fields = ["model_key", "prompt"]
    ordering = ["model_key"]
    assist = False
