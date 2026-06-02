"""Structured autonomous branch selection for decision-tree traversal."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from advocate_bot_qualtrics.config import (
    get_anthropic_chat_model,
    load_autonomous_system_prompt,
)
from advocate_bot_qualtrics.decision_tree.autonomous_schemas import (
    AutoNode,
    AutonomousStepSelection,
)
from advocate_bot_qualtrics.decision_tree.errors import ChatError
from advocate_bot_qualtrics.llm.client import AnthropicClient
from advocate_bot_qualtrics.schemas.complaint_fact_sheet import ComplaintFactSheet

AUTO_TOOL_NAME = "submit_autonomous_step"


def _autonomous_tool_schema() -> dict[str, Any]:
    return {
        "name": AUTO_TOOL_NAME,
        "description": "Select the next branch for autonomous decision-tree traversal.",
        "input_schema": AutonomousStepSelection.model_json_schema(),
    }


def _parse_tool_use(response: Any) -> dict[str, Any]:
    for block in response.content:
        if block.type == "tool_use" and block.name == AUTO_TOOL_NAME:
            return block.input
    raise ChatError(f"Anthropic response did not include tool_use block '{AUTO_TOOL_NAME}'.")


def select_autonomous_branch(
    *,
    node: AutoNode,
    fact_sheet: ComplaintFactSheet,
) -> AutonomousStepSelection:
    """Select a branch for the given autonomous node using Anthropic structured output."""
    client = AnthropicClient()
    system = load_autonomous_system_prompt()
    payload = {
        "node": node.model_dump(mode="json"),
        "complaint_fact_sheet": fact_sheet.model_dump(mode="json", exclude={"field_citations"}),
    }

    response = client.complete(
        model=get_anthropic_chat_model(),
        system=system,
        messages=[{"role": "user", "content": str(payload)}],
        temperature=0.0,
        tools=[_autonomous_tool_schema()],
        tool_choice={"type": "tool", "name": AUTO_TOOL_NAME},
    )

    tool_input = _parse_tool_use(response)
    try:
        return AutonomousStepSelection.model_validate(tool_input)
    except ValidationError as exc:
        raise ChatError("LLM output failed autonomous step schema validation.") from exc
