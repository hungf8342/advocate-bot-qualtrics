"""Annotate party role terms with names from the complaint fact sheet."""

from __future__ import annotations

import re

from advocate_bot_qualtrics.schemas.complaint_fact_sheet import ComplaintFactSheet

_ORIGINAL_CREDITOR_RE = re.compile(
    r"\boriginal creditor\b(?!\s*\()",
    re.IGNORECASE,
)
_DEBT_COLLECTOR_RE = re.compile(
    r"\bdebt collector\b(?!\s*\()",
    re.IGNORECASE,
)


def annotate_party_terms(text: str, facts: ComplaintFactSheet) -> str:
    """Append (Name) after role phrases when names are present in the fact sheet."""
    if not text:
        return text

    result = text
    if facts.original_creditor_name:
        result = _ORIGINAL_CREDITOR_RE.sub(
            f"original creditor ({facts.original_creditor_name})",
            result,
        )
    if facts.debt_collector_name:
        result = _DEBT_COLLECTOR_RE.sub(
            f"debt collector ({facts.debt_collector_name})",
            result,
        )
    return result
