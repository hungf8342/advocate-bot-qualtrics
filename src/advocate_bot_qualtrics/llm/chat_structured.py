"""Structured clarification responses for the clickthrough."""

from __future__ import annotations

from typing import Any

from advocate_bot_qualtrics.config import (
    CHAT_TOOL_NAME,
    get_chat_provider,
    get_zai_api_key,
    get_zai_base_url,
    get_zai_chat_model,
)
from advocate_bot_qualtrics.core.errors import ChatError
from advocate_bot_qualtrics.core.schemas import ChatTurnResponse
from advocate_bot_qualtrics.llm.client import OpenAIClient
from pydantic import ValidationError


def _chat_turn_openai_tool() -> dict[str, Any]:
    schema = ChatTurnResponse.model_json_schema()
    return {
        "type": "function",
        "function": {
            "name": CHAT_TOOL_NAME,
            "description": "Submit the clickthrough clarification response.",
            "parameters": schema,
        },
    }


def _submit_chat_turn_zai(*, system: str, payload: dict[str, Any]) -> ChatTurnResponse:
    """Call Z.ai (GLM) with forced function calling and validate the response."""
    api_key = get_zai_api_key()
    if not api_key:
        raise ChatError("ZAI_API_KEY is not set.")

    client = OpenAIClient(api_key=api_key, base_url=get_zai_base_url())
    user_text = payload if isinstance(payload, str) else str(payload)

    tool_input = client.complete_with_tools(
        model=get_zai_chat_model(),
        system=system,
        messages=[{"role": "user", "content": user_text}],
        tools=[_chat_turn_openai_tool()],
        tool_choice={"type": "function", "function": {"name": CHAT_TOOL_NAME}},
    )

    try:
        return ChatTurnResponse.model_validate(tool_input)
    except ValidationError as exc:
        raise ChatError("LLM output failed chat schema validation.") from exc


def submit_chat_turn(*, system: str, payload: dict[str, Any]) -> ChatTurnResponse:
    if get_chat_provider() != "zai":
        raise ChatError(
            "Only CHAT_PROVIDER=zai is supported for clickthrough clarification."
        )
    return _submit_chat_turn_zai(system=system, payload=payload)
