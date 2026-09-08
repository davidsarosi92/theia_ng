"""Built-in providers. All stdlib HTTP — no SDK, no new dependency.

``openai_compatible`` covers the large majority of deployments: Ollama,
llama.cpp server, vLLM, LM Studio, OpenRouter, Groq, Together, and OpenAI itself
all speak ``POST /v1/chat/completions``. Anthropic's Messages API has a
different shape, so it gets its own small provider.
"""

from __future__ import annotations

from typing import Any

from theia_ng.llm.base import LLMError, LLMProvider


class OpenAICompatibleProvider(LLMProvider):
    """Any endpoint exposing ``/v1/chat/completions``.

    ``BASE_URL`` is the part up to and including ``/v1`` — e.g.
    ``http://ollama:11434/v1`` or ``https://api.openai.com/v1``.
    """

    supports_schema = True

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self.base_url = (config.get("BASE_URL") or "").rstrip("/")
        if not self.base_url:
            raise LLMError("THEIA_NG['LLM']['BASE_URL'] is not set")
        self.api_key = config.get("API_KEY") or ""

    def complete(self, system: str, user: str, schema: dict[str, Any] | None) -> str:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            # Deterministic: the same sentence must produce the same filter.
            "temperature": 0,
            "stream": False,
        }
        if schema is not None:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "list_state", "strict": True, "schema": schema},
            }
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        data = self._post_json(f"{self.base_url}/chat/completions", payload, headers)
        try:
            return data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError("Unexpected chat/completions response shape") from exc


class AnthropicProvider(LLMProvider):
    """Anthropic Messages API (``/v1/messages``).

    No structured-output mode is requested; correctness comes from
    validate-and-retry in ``assist``, which every provider needs anyway.
    """

    supports_schema = False

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self.base_url = (config.get("BASE_URL") or "https://api.anthropic.com/v1").rstrip("/")
        self.api_key = config.get("API_KEY") or ""
        if not self.api_key:
            raise LLMError("THEIA_NG['LLM']['API_KEY'] is required for the anthropic provider")
        self.version = config.get("ANTHROPIC_VERSION", "2023-06-01")
        self.max_tokens = int(config.get("MAX_TOKENS", 512))

    def complete(self, system: str, user: str, schema: dict[str, Any] | None) -> str:
        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            # No `temperature`: the sampling parameters were removed on the current
            # Claude models (Opus 5, Sonnet 5, Opus 4.8/4.7 and later) and sending
            # one returns a 400. Determinism is not available there; correctness
            # comes from validate-and-retry in `assist` instead.
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        headers = {"x-api-key": self.api_key, "anthropic-version": self.version}
        data = self._post_json(f"{self.base_url}/messages", payload, headers)
        try:
            parts = [b.get("text", "") for b in data["content"] if b.get("type") == "text"]
        except (KeyError, TypeError) as exc:
            raise LLMError("Unexpected messages response shape") from exc
        return "".join(parts)


BUILTIN_PROVIDERS = {
    "openai_compatible": OpenAICompatibleProvider,
    "anthropic": AnthropicProvider,
}
