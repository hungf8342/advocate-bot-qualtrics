"""Session state and routing helpers for the interactive decision tree."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from advocate_bot_qualtrics.decision_tree.interactive_tree import (
    INTERACTIVE_HOOK_ADVANCES,
    INTERACTIVE_HOOK_NODE_IDS,
)
from advocate_bot_qualtrics.schemas.complaint_fact_sheet import ComplaintFactSheet

_DATE_SUBMIT_NODES: dict[str, str] = {
    "get_filing_date": "filing_date",
    "get_last_payment_complaint": "last_payment_complaint",
    "get_last_payment_OG_creditor": "last_payment_og_creditor",
    "get_last_payment_debt_collector": "last_payment_debt_collector",
}

_FDCPA_FLAG_NODES: dict[str, str] = {
    "threatening_arrest": "threatened",
    "contact_third_parties": "disclosed",
    "record_bad_behavior": "evidence",
}


@dataclass
class InteractiveSessionState:
    filing_date: date | None = None
    last_payment_complaint: date | None = None
    last_payment_og_creditor: date | None = None
    last_payment_debt_collector: date | None = None
    threatened: bool = False
    disclosed: bool = False
    evidence: bool = False


def init_session_from_fact_sheet(facts: ComplaintFactSheet) -> InteractiveSessionState:
    """Seed SOL dates from extracted complaint facts."""
    return InteractiveSessionState(
        filing_date=facts.date_complaint_filed,
        last_payment_complaint=facts.date_user_failed_to_pay,
    )


def is_interactive_hook_node(node_id: str) -> bool:
    return node_id in INTERACTIVE_HOOK_NODE_IDS


def advance_from_hook(node_id: str) -> str | None:
    return INTERACTIVE_HOOK_ADVANCES.get(node_id)


def apply_interactive_branch(
    session: InteractiveSessionState,
    node_id: str,
    branch_id: str,
    *,
    submitted_date: date | None = None,
) -> None:
    """Update session flags and collected dates after a user answers a node."""
    if node_id in _DATE_SUBMIT_NODES and branch_id == "submit":
        field = _DATE_SUBMIT_NODES[node_id]
        setattr(session, field, submitted_date)

    if node_id in _FDCPA_FLAG_NODES and branch_id == "yes":
        field = _FDCPA_FLAG_NODES[node_id]
        setattr(session, field, True)
