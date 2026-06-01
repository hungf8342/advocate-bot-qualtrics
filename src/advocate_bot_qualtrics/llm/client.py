"""Thin LLM client wrappers for Anthropic and OpenAI."""

from __future__ import annotations

from typing import Any

import anthropic
import openai


class AnthropicClient:
    """Wrapper around Anthropic SDK."""

    def __init__(self) -> None:
        self._client = anthropic.Anthropic()

    def complete(
        self,
        *,
        model: str,
        system: str,
        messages: list[dict[str, Any]],
        temperature: float = 0.0,
        max_tokens: int = 8192,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: dict[str, Any] | str | None = None,
    ) -> Any:
        request: dict[str, Any] = {
            "model": model,
            "system": system,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            request["tools"] = tools
        if tool_choice is not None:
            request["tool_choice"] = tool_choice
        return self._client.messages.create(**request)


class OpenAIClient:
    """Wrapper around OpenAI SDK structured parse."""

    def __init__(self) -> None:
        self._client = openai.OpenAI()

    @property
    def raw(self) -> openai.OpenAI:
        return self._client
