"""OpenAI-compatible client for clickthrough clarification."""

from __future__ import annotations

import json
from typing import Any

import openai


class OpenAIClient:
    """Wrapper around OpenAI SDK (also used for Z.ai's OpenAI-compatible API)."""

    def __init__(self, *, api_key: str | None = None, base_url: str | None = None) -> None:
        kwargs: dict[str, str] = {}
        if api_key is not None:
            kwargs["api_key"] = api_key
        if base_url is not None:
            kwargs["base_url"] = base_url
        self._client = openai.OpenAI(**kwargs)

    @property
    def raw(self) -> openai.OpenAI:
        return self._client

    def complete_with_tools(
        self,
        *,
        model: str,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        tool_choice: dict[str, Any],
        temperature: float = 0.0,
        max_tokens: int = 8192,
    ) -> dict[str, Any]:
        response = self._client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system}, *messages],
            tools=tools,
            tool_choice=tool_choice,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        message = response.choices[0].message
        if not message.tool_calls:
            raise RuntimeError("Z.ai response did not include tool_calls.")
        tool_call = message.tool_calls[0]
        if tool_call.function.name is None:
            raise RuntimeError("Z.ai tool call missing function name.")
        try:
            return json.loads(tool_call.function.arguments)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Z.ai tool call arguments were not valid JSON.") from exc
