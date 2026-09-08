"""Provider-agnostic LLM seam.

The core of Theia NG depends only on ``django.contrib.auth``; this package adds
**no** new dependency. Every built-in provider talks HTTP with stdlib
``urllib.request``, so "swap the provider" is a settings change, never a pip
install.

A provider does exactly one thing: given a system prompt, a user message and a
JSON schema the answer must satisfy, return the model's raw text. Everything
above it (schema slicing, validation, retries) is provider-independent and lives
in ``theia_ng.llm.assist``.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any


class LLMError(Exception):
    """Any failure talking to the model. Always recoverable by the caller: the
    assist endpoint degrades to "could not interpret" and the manual filter UI
    stays available."""


class LLMProvider:
    """Base class. Subclass and implement :meth:`complete`."""

    #: Whether this provider can enforce a JSON schema during decoding. When it
    #: cannot, ``assist`` leans harder on validate-and-retry — never assume a
    #: provider's grammar covers the whole value space (measured: Ollama honours
    #: ``enum`` but ignores a nested ``anyOf``/``pattern``).
    supports_schema: bool = False

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.model = config.get("MODEL") or ""
        self.timeout = float(config.get("TIMEOUT", 20))
        if not self.model:
            raise LLMError("THEIA_NG['LLM']['MODEL'] is not set")

    def complete(self, system: str, user: str, schema: dict[str, Any] | None) -> str:
        raise NotImplementedError

    # -- shared HTTP helper -------------------------------------------------
    def _post_json(self, url: str, payload: dict, headers: dict[str, str]) -> dict:
        body = json.dumps(payload).encode()
        req = urllib.request.Request(
            url, data=body, headers={"Content-Type": "application/json", **headers}
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                # Cap the read: a misbehaving endpoint must not stream us out of memory.
                raw = resp.read(2_000_000)
        except urllib.error.HTTPError as exc:  # 4xx/5xx from the endpoint
            detail = exc.read(2000).decode(errors="replace") if hasattr(exc, "read") else ""
            raise LLMError(f"LLM endpoint returned {exc.code}: {detail[:300]}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise LLMError(f"LLM endpoint unreachable: {exc}") from exc
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise LLMError("LLM endpoint returned a non-JSON body") from exc
