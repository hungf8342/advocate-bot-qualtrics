"""Provider-specific structured extraction into ComplaintFactSheet."""

from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from advocate_bot_qualtrics.config import (
    TOOL_NAME,
    get_anthropic_model,
    get_llm_provider,
    get_openai_model,
    load_system_prompt,
)
from advocate_bot_qualtrics.extraction.errors import ExtractionError
from advocate_bot_qualtrics.llm.client import AnthropicClient, OpenAIClient
from advocate_bot_qualtrics.schemas.complaint_fact_sheet import ComplaintFactSheet

T = TypeVar("T", bound=BaseModel)


def _complaint_fact_sheet_tool() -> dict[str, Any]:
    return {
        "name": TOOL_NAME,
        "description": "Submit the extracted complaint fact sheet.",
        "input_schema": ComplaintFactSheet.model_json_schema(),
    }


def _parse_anthropic_tool_response(response: Any) -> dict[str, Any]:
    for block in response.content:
        if block.type == "tool_use" and block.name == TOOL_NAME:
            return block.input
    raise ExtractionError(
        f"Anthropic response did not include tool_use block '{TOOL_NAME}'."
    )


def _validate(model: type[T], data: Any) -> T:
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise ExtractionError("LLM output failed schema validation.") from exc


def extract_with_anthropic(
    *,
    system: str,
    user_text: str,
    model: str | None = None,
) -> ComplaintFactSheet:
    client = AnthropicClient()
    response = client.complete(
        model=model or get_anthropic_model(),
        system=system,
        messages=[{"role": "user", "content": user_text}],
        temperature=0.0,
        tools=[_complaint_fact_sheet_tool()],
        tool_choice={"type": "tool", "name": TOOL_NAME},
    )
    payload = _parse_anthropic_tool_response(response)
    return _validate(ComplaintFactSheet, payload)


def extract_with_openai(
    *,
    system: str,
    user_text: str,
    model: str | None = None,
) -> ComplaintFactSheet:
    client = OpenAIClient()
    completion = client.raw.beta.chat.completions.parse(
        model=model or get_openai_model(),
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_text},
        ],
        response_format=ComplaintFactSheet,
        temperature=0.0,
    )
    message = completion.choices[0].message
    if message.refusal:
        raise ExtractionError(f"OpenAI refused extraction: {message.refusal}")
    parsed = message.parsed
    if parsed is None:
        raise ExtractionError("OpenAI returned no parsed ComplaintFactSheet.")
    return parsed


def extract_structured_complaint_facts(
    user_text: str,
    *,
    provider: str | None = None,
    model: str | None = None,
) -> ComplaintFactSheet:
    """Route extraction to the configured or requested LLM provider."""
    system = load_system_prompt()
    selected = (provider or get_llm_provider()).strip().lower()

    if selected == "anthropic":
        return extract_with_anthropic(system=system, user_text=user_text, model=model)
    if selected == "openai":
        return extract_with_openai(system=system, user_text=user_text, model=model)

    raise ValueError(
        f"Unsupported LLM provider '{selected}'. Use 'anthropic' or 'openai'."
    )
