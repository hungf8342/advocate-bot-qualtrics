"""Structured chat responses for the decision tree."""

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
            "description": "Submit the decision-tree chat turn.",
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


# --- Previous Haiku / Anthropic path (commented out; set CHAT_PROVIDER=anthropic and restore) ---
#
# from advocate_bot_qualtrics.config import get_anthropic_chat_model
# from advocate_bot_qualtrics.llm.client import AnthropicClient
#
#
# def _chat_turn_tool() -> dict[str, Any]:
#     return {
#         "name": CHAT_TOOL_NAME,
#         "description": "Submit the decision-tree chat turn.",
#         "input_schema": ChatTurnResponse.model_json_schema(),
#     }
#
#
# def _parse_anthropic_tool_use(response: Any) -> dict[str, Any]:
#     for block in response.content:
#         if block.type == "tool_use" and block.name == CHAT_TOOL_NAME:
#             return block.input
#     raise ChatError(f"Anthropic response did not include tool_use block '{CHAT_TOOL_NAME}'.")
#
#
# def _submit_chat_turn_anthropic(*, system: str, payload: dict[str, Any]) -> ChatTurnResponse:
#     client = AnthropicClient()
#     user_text = payload if isinstance(payload, str) else str(payload)
#     response = client.complete(
#         model=get_anthropic_chat_model(),
#         system=system,
#         messages=[{"role": "user", "content": user_text}],
#         temperature=0.0,
#         tools=[_chat_turn_tool()],
#         tool_choice={"type": "tool", "name": CHAT_TOOL_NAME},
#     )
#     tool_input = _parse_anthropic_tool_use(response)
#     try:
#         return ChatTurnResponse.model_validate(tool_input)
#     except ValidationError as exc:
#         raise ChatError("LLM output failed chat schema validation.") from exc


def submit_chat_turn(*, system: str, payload: dict[str, Any]) -> ChatTurnResponse:
    if get_chat_provider() == "anthropic":
        raise ChatError(
            "CHAT_PROVIDER=anthropic is disabled; restore _submit_chat_turn_anthropic in "
            "chat_structured.py or set CHAT_PROVIDER=zai."
        )
    return _submit_chat_turn_zai(system=system, payload=payload)
