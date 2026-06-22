"""LLM client for generating simulated defendant user messages."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from advocate_bot_qualtrics.decision_tree.errors import ChatError
from advocate_bot_qualtrics.llm.client import AnthropicClient
from advocate_bot_qualtrics.schemas.complaint_fact_sheet import ComplaintFactSheet
from advocate_bot_qualtrics.simulator.config import (
    SIMULATOR_TOOL_NAME,
    get_simulator_user_model,
    load_simulator_user_system_prompt,
)
from advocate_bot_qualtrics.simulator.schemas import SimulatorUserTurn


def _simulator_tool_schema() -> dict[str, Any]:
    return {
        "name": SIMULATOR_TOOL_NAME,
        "description": "Submit the simulated defendant's next user message.",
        "input_schema": SimulatorUserTurn.model_json_schema(),
    }


def _parse_tool_use(response: Any) -> dict[str, Any]:
    for block in response.content:
        if block.type == "tool_use" and block.name == SIMULATOR_TOOL_NAME:
            return block.input
    raise ChatError(
        f"Anthropic response did not include tool_use block '{SIMULATOR_TOOL_NAME}'."
    )


def build_simulator_system_prompt(*, persona: str) -> str:
    base = load_simulator_user_system_prompt()
    persona_block = persona.strip() or "Cooperative defendant who answers questions directly."
    return f"{base}\n\n## Persona\n\n{persona_block}\n"


def generate_simulator_user_reply(
    *,
    persona: str,
    facts: ComplaintFactSheet,
    transcript: list[tuple[str, str]],
    last_assistant_message: str,
) -> SimulatorUserTurn:
    """Generate the next simulated user message."""
    client = AnthropicClient()
    system = build_simulator_system_prompt(persona=persona)
    payload = {
        "complaint_fact_sheet": facts.model_dump(mode="json", exclude={"field_citations"}),
        "transcript": [
            {"role": role, "content": text}
            for role, text in transcript
        ],
        "last_assistant_message": last_assistant_message,
    }

    response = client.complete(
        model=get_simulator_user_model(),
        system=system,
        messages=[{"role": "user", "content": str(payload)}],
        temperature=0.7,
        tools=[_simulator_tool_schema()],
        tool_choice={"type": "tool", "name": SIMULATOR_TOOL_NAME},
    )

    tool_input = _parse_tool_use(response)
    try:
        return SimulatorUserTurn.model_validate(tool_input)
    except ValidationError as exc:
        raise ChatError("Simulator LLM output failed schema validation.") from exc
