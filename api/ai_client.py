"""AI providers. Each company chooses its own provider, model and API key (stored encrypted); the platform never mixes them.

The rest of the platform only calls `draft_json` / `test_key` here. Adding a provider means adding one class with the same two methods and one
registry entry; the prompt, the output schema, the quote checking and the accept / reject flow are provider-neutral.
Tests inject a stand-in client with `ai_client.CLIENT` (used by the Anthropic provider instead of the real SDK).
"""
from __future__ import annotations
import json
from typing import Any

import config

CLIENT: Any = None                      # tests inject a stand-in with the same .beta.messages.create / .messages.create / .models.retrieve surface


class AIError(Exception):
    """Message is safe to show to the user."""


class AnthropicProvider:
    id, label = "anthropic", "Anthropic (Claude)"
    default_model = "claude-opus-5-5"
    key_hint = "Keys start with sk-ant-. Create one at console.anthropic.com > Settings > API keys."
    available = True

    @staticmethod
    def check_key(key: str) -> None:
        if not key.startswith("sk-ant-") or len(key) < 20:
            raise AIError("That doesn't look like an Anthropic key (they start with sk-ant-).")

    @staticmethod
    def _client(key: str):
        if CLIENT is not None:
            return CLIENT
        import anthropic
        return anthropic.Anthropic(api_key=key, timeout=600.0, max_retries=2)

    @staticmethod
    def _friendly(e: Exception) -> AIError:
        name = e.__class__.__name__
        if name == "AuthenticationError":
            return AIError("The AI service did not accept this key. Check it in the AI settings.")
        if name == "PermissionDeniedError":
            return AIError("This key is not allowed to use that model. Check the account and the model name.")
        if name == "NotFoundError":
            return AIError("The AI service does not know that model name. Check it in the AI settings.")
        if name == "RateLimitError":
            return AIError("The AI service is busy or the account is out of credit. Try again shortly, or check the Anthropic account.")
        if name in ("APITimeoutError", "APIConnectionError"):
            return AIError("The AI service could not be reached. Try again.")
        return AIError("The AI service returned an error. Try again; if it keeps happening, quote the time to support.")

    def test(self, key: str, model: str) -> str:
        """Free check that the key works and the model exists (no tokens are used)."""
        try:
            m = self._client(key).models.retrieve(model)
        except Exception as e:                                      # noqa: BLE001
            raise self._friendly(e)
        return getattr(m, "display_name", None) or model

    def draft_json(self, key: str, model: str, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        client = self._client(key)
        kw: dict[str, Any] = dict(model=model, max_tokens=16000, system=system, messages=[{"role": "user", "content": user}],
                                  output_config={"effort": "high", "format": {"type": "json_schema", "schema": schema}})
        try:
            try:   # server-side fallback if the main model declines a request (Claude API default for this model family)
                resp = client.beta.messages.create(**kw, betas=["server-side-fallback-2026-07-01"], fallbacks="default")
            except Exception as e:                   # noqa: BLE001 - an endpoint rejecting the beta field: retry plainly once
                if e.__class__.__name__ in ("BadRequestError", "TypeError"):
                    resp = client.messages.create(**kw)
                else:
                    raise
        except AIError:
            raise
        except Exception as e:                       # noqa: BLE001
            raise self._friendly(e)
        if getattr(resp, "stop_reason", "") == "refusal":
            raise AIError("The AI declined this request. Nothing was drafted.")
        if getattr(resp, "stop_reason", "") == "max_tokens":
            raise AIError("The AI ran out of room before finishing. Select fewer documents and try again.")
        text = next((b.text for b in resp.content if getattr(b, "type", "") == "text"), "")
        try:
            data = json.loads(text)
        except ValueError:
            raise AIError("The AI's answer could not be read. Nothing was drafted; try again.")
        if not isinstance(data, dict) or not isinstance(data.get("items"), list):
            raise AIError("The AI's answer was not in the expected shape. Nothing was drafted; try again.")
        return data


class PlannedProvider:
    available = False
    def __init__(self, id: str, label: str, model: str, hint: str):
        self.id, self.label, self.default_model, self.key_hint = id, label, model, hint


PROVIDERS: dict[str, Any] = {
    "anthropic": AnthropicProvider(),
    "openai": PlannedProvider("openai", "OpenAI (GPT)", "", "Planned"),
    "google": PlannedProvider("google", "Google (Gemini)", "", "Planned"),
}


def get(provider_id: str):
    p = PROVIDERS.get(provider_id)
    if p is None or not p.available:
        raise AIError("That AI provider is not available yet.")
    return p


def catalogue() -> list[dict[str, Any]]:
    return [{"id": p.id, "label": p.label, "available": p.available, "default_model": p.default_model, "key_hint": p.key_hint} for p in PROVIDERS.values()]


def platform_key(provider_id: str) -> str:
    """A server-wide key, used only when the operator has explicitly allowed it (a managed-service arrangement). Customers use their own."""
    return config.ANTHROPIC_API_KEY if (provider_id == "anthropic" and config.AI_ALLOW_PLATFORM_KEY) else ""
