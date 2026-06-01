"""Public API for complaint fact extraction."""

from __future__ import annotations

from advocate_bot_qualtrics.config import MAX_COMPLAINT_CHARS
from advocate_bot_qualtrics.extraction.errors import ExtractionError
from advocate_bot_qualtrics.llm.structured import extract_structured_complaint_facts
from advocate_bot_qualtrics.schemas.complaint_fact_sheet import ComplaintFactSheet

__all__ = ["ExtractionError", "extract_complaint_facts"]


def _prepare_complaint_text(raw_text: str) -> str:
    stripped = raw_text.strip()
    if not stripped:
        raise ValueError("Complaint text is empty.")

    if len(stripped) <= MAX_COMPLAINT_CHARS:
        return stripped

    truncated = stripped[:MAX_COMPLAINT_CHARS]
    return (
        f"{truncated}\n\n"
        "[NOTE: Complaint text was truncated to fit context limits. "
        "Extract only from the text above.]"
    )


def extract_complaint_facts(
    raw_text: str,
    *,
    provider: str | None = None,
    model: str | None = None,
) -> ComplaintFactSheet:
    """Extract a ComplaintFactSheet from raw complaint text via an LLM.

    Uses Anthropic tool calling or OpenAI structured outputs depending on
    ``provider`` or the ``LLM_PROVIDER`` environment variable.

    Date fields are null when not explicitly stated in the complaint.
    """
    user_text = _prepare_complaint_text(raw_text)
    return extract_structured_complaint_facts(
        user_text,
        provider=provider,
        model=model,
    )
