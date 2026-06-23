"""Structured chat responses for the decision tree."""

from __future__ import annotations

from typing import Any

from advocate_bot_qualtrics.config import (
    CHAT_TOOL_NAME,
    get_anthropic_chat_model,
)
from advocate_bot_qualtrics.core.errors import ChatError
from advocate_bot_qualtrics.core.schemas import ChatTurnResponse
from advocate_bot_qualtrics.llm.client import AnthropicClient
from pydantic import ValidationError


def _chat_turn_tool() -> dict[str, Any]:
    return {
        "name": CHAT_TOOL_NAME,
        "description": "Submit the decision-tree chat turn.",
        "input_schema": ChatTurnResponse.model_json_schema(),
    }


def _parse_anthropic_tool_use(response: Any) -> dict[str, Any]:
    for block in response.content:
        if block.type == "tool_use" and block.name == CHAT_TOOL_NAME:
            return block.input
    raise ChatError(f"Anthropic response did not include tool_use block '{CHAT_TOOL_NAME}'.")


def submit_chat_turn(*, system: str, payload: dict[str, Any]) -> ChatTurnResponse:
    """Call Anthropic with a forced tool schema and validate the response."""

    client = AnthropicClient()

    user_text = payload if isinstance(payload, str) else str(payload)

    response = client.complete(
        model=get_anthropic_chat_model(),
        system=system,
        messages=[{"role": "user", "content": user_text}],
        temperature=0.0,
        tools=[_chat_turn_tool()],
        tool_choice={"type": "tool", "name": CHAT_TOOL_NAME},
    )

    tool_input = _parse_anthropic_tool_use(response)

    try:
        return ChatTurnResponse.model_validate(tool_input)
    except ValidationError as exc:
        raise ChatError("LLM output failed chat schema validation.") from exc
