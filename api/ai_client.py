"""The one place the platform calls Claude. Everything else is testable without it: tests set `ai_client.CLIENT` to a stand-in object."""
from __future__ import annotations
import json
from typing import Any

import config

CLIENT: Any = None                      # tests inject a stand-in with the same .beta.messages.create / .messages.create surface


class AIError(Exception):
    """Message is safe to show to the user."""


def configured() -> bool:
    return CLIENT is not None or bool(config.ANTHROPIC_API_KEY)


def _client():
    if CLIENT is not None:
        return CLIENT
    import anthropic
    return anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY, timeout=600.0, max_retries=2)


def draft_json(system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
    """One structured-output request. Returns the parsed JSON. Raises AIError with a plain-language message."""
    client = _client()
    kw: dict[str, Any] = dict(model=config.AI_MODEL, max_tokens=16000, system=system, messages=[{"role": "user", "content": user}],
                              output_config={"effort": "high", "format": {"type": "json_schema", "schema": schema}})
    try:
        try:   # server-side fallback if the main model declines a request (Claude API default for this model family)
            resp = client.beta.messages.create(**kw, betas=["server-side-fallback-2026-07-01"], fallbacks="default")
        except Exception as e:                       # noqa: BLE001 - an older or different endpoint rejecting the beta field: retry plainly once
            if e.__class__.__name__ in ("BadRequestError", "TypeError"):
                resp = client.messages.create(**kw)
            else:
                raise
    except AIError:
        raise
    except Exception as e:                           # noqa: BLE001
        name = e.__class__.__name__
        if name == "AuthenticationError":
            raise AIError("The AI service did not accept the platform's key. Check the Anthropic key on the server.")
        if name == "RateLimitError":
            raise AIError("The AI service is busy or the account is out of credit. Try again shortly, or check the Anthropic account.")
        if name in ("APITimeoutError", "APIConnectionError"):
            raise AIError("The AI service could not be reached. Try again.")
        raise AIError("The AI service returned an error. Try again; if it keeps happening, quote the time to support.")
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
