"""Session state and routing helpers for consumer debt interactive tree."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from advocate_bot_qualtrics.core.session import NodeAnswerRecord, record_node_answer
from advocate_bot_qualtrics.practice_areas.consumer_debt.tree import (
    INTERACTIVE_HOOK_ADVANCES,
    INTERACTIVE_HOOK_NODE_IDS,
)

_DATE_SUBMIT_NODES: dict[str, str] = {
    "get_filing_date": "filing_date",
    "get_last_payment_complaint": "last_payment_complaint",
    "get_last_payment_OG_creditor": "last_payment_og_creditor",
    "get_last_payment_debt_collector": "last_payment_debt_collector",
}

_TEXT_SUBMIT_NODES: dict[str, str] = {
    "get_plaintiff_name": "plaintiff_name",
    "get_amount_sued": "amount_sued",
}

_YES_WITH_DATE_NODES: dict[str, str] = {
    "additional_payment_OG_creditor": "last_payment_og_creditor",
    "additional_payment_debt_collector": "last_payment_debt_collector",
}

_FDCPA_FLAG_NODES: dict[str, str] = {
    "threatening_arrest": "threatened",
    "contact_third_parties": "disclosed",
    "record_bad_behavior": "evidence",
}


@dataclass
class InteractiveSessionState:
    plaintiff_name: str | None = None
    amount_sued: str | None = None
    filing_date: date | None = None
    last_payment_complaint: date | None = None
    last_payment_og_creditor: date | None = None
    last_payment_debt_collector: date | None = None
    filing_date_changed: bool = False
    last_payment_date_changed: bool = False
    threatened: bool = False
    disclosed: bool = False
    evidence: bool = False
    node_answers: dict[str, NodeAnswerRecord] = field(default_factory=dict)


def init_session() -> InteractiveSessionState:
    """Start a blank, in-memory session populated only by user answers."""
    return InteractiveSessionState()


def is_interactive_hook_node(node_id: str) -> bool:
    return node_id in INTERACTIVE_HOOK_NODE_IDS


def advance_from_hook(node_id: str) -> str | None:
    return INTERACTIVE_HOOK_ADVANCES.get(node_id)


def is_date_submit_node(node_id: str) -> bool:
    return node_id in _DATE_SUBMIT_NODES


def apply_interactive_branch(
    session: InteractiveSessionState,
    node_id: str,
    branch_id: str,
    *,
    submitted_date: date | None = None,
    submitted_text: str | None = None,
) -> None:
    """Update session flags and collected dates after a user answers a node."""
    if node_id in _DATE_SUBMIT_NODES and branch_id == "submit":
        if submitted_date is not None:
            field_name = _DATE_SUBMIT_NODES[node_id]
            setattr(session, field_name, submitted_date)
    if node_id in _TEXT_SUBMIT_NODES and branch_id == "submit" and submitted_text:
        setattr(session, _TEXT_SUBMIT_NODES[node_id], submitted_text.strip())

    if node_id in _YES_WITH_DATE_NODES and branch_id == "yes" and submitted_date is not None:
        field_name = _YES_WITH_DATE_NODES[node_id]
        setattr(session, field_name, submitted_date)

    if node_id in _FDCPA_FLAG_NODES and branch_id == "yes":
        field_name = _FDCPA_FLAG_NODES[node_id]
        setattr(session, field_name, True)


__all__ = [
    "InteractiveSessionState",
    "NodeAnswerRecord",
    "advance_from_hook",
    "apply_interactive_branch",
    "init_session",
    "is_date_submit_node",
    "is_interactive_hook_node",
    "record_node_answer",
]
