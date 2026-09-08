"""Optional LLM assistant: natural language -> a validated list filter state.

Off unless configured. Adding no dependency is a hard requirement — the built-in
providers speak HTTP through stdlib ``urllib``, so pointing Theia at Ollama,
vLLM, OpenAI, Anthropic or anything OpenAI-compatible is a settings change::

    THEIA_NG = {
        "LLM": {
            "PROVIDER": "openai_compatible",     # or "anthropic", or a dotted path
            "BASE_URL": "http://ollama:11434/v1",
            "MODEL": "qwen2.5:7b",
            "API_KEY": os.getenv("THEIA_LLM_API_KEY", ""),
            "TIMEOUT": 20,
            "MAX_RETRIES": 1,
            # Optional rollout gate. Empty means "every registered model"; list
            # model keys to switch the assistant on for those only. To turn it
            # off for one model, prefer `ModelAdmin.assist = False` — that lives
            # with the rest of that model's config.
            "ALLOW_MODELS": [],
        },
    }

Imports stay lazy so ``import theia_ng`` costs nothing when the feature is off.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from theia_ng.llm.base import LLMError, LLMProvider

if TYPE_CHECKING:
    from theia_ng.options import ModelAdmin

__all__ = ["LLMError", "LLMProvider", "llm_config", "is_enabled", "model_allowed",
           "resolve_provider"]


def llm_config() -> dict[str, Any]:
    """The effective ``THEIA_NG['LLM']`` dict (admin overrides applied)."""
    from theia_ng.siteconfig import conf

    raw = conf().get("LLM") or {}
    return dict(raw) if isinstance(raw, dict) else {}


def is_enabled() -> bool:
    """True when a usable LLM is configured. Everything else keys off this."""
    cfg = llm_config()
    return bool(cfg.get("MODEL")) and bool(cfg.get("PROVIDER", "openai_compatible"))


def model_allowed(model_key: str, admin: ModelAdmin | None = None) -> bool:
    """Whether the assistant may be offered for this model.

    Two switches, deliberately at different levels:

    * ``ModelAdmin.assist = False`` — opt one model out, in code, next to the
      rest of that model's configuration.
    * ``ALLOW_MODELS`` — a deploy-level rollout gate that host code cannot
      override. Empty (the default) means every registered model.

    A denylist setting would only duplicate the first of these, so there isn't
    one: "all except a few" is expressed by ``assist = False`` on those few.
    """
    if admin is not None and getattr(admin, "assist", True) is False:
        return False
    allow = {str(k) for k in (llm_config().get("ALLOW_MODELS") or [])}
    return not allow or model_key in allow


def resolve_provider() -> LLMProvider:
    """Instantiate the configured provider. Raises :class:`LLMError` if unusable."""
    cfg = llm_config()
    name = str(cfg.get("PROVIDER") or "openai_compatible")

    from theia_ng.llm.providers import BUILTIN_PROVIDERS

    cls = BUILTIN_PROVIDERS.get(name)
    if cls is None:
        # A dotted path lets a host project plug in its own provider without a
        # patch — same escape hatch the data adapters offer.
        if "." not in name:
            raise LLMError(
                f"Unknown LLM provider {name!r}; expected one of "
                f"{sorted(BUILTIN_PROVIDERS)} or a dotted import path"
            )
        from django.utils.module_loading import import_string

        try:
            cls = import_string(name)
        except ImportError as exc:
            raise LLMError(f"Could not import LLM provider {name!r}") from exc
    return cls(cfg)
