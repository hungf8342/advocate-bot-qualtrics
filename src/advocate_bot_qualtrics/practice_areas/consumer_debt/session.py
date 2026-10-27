"""Session state and routing helpers for consumer debt interactive tree."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from advocate_bot_qualtrics.core.session import NodeAnswerRecord, record_node_answer
from advocate_bot_qualtrics.practice_areas.consumer_debt.preliminary import (
    PreliminaryField,
    collect_preliminary_answer,
    load_complaint_fields,
)
from advocate_bot_qualtrics.practice_areas.consumer_debt.tree import (
    INTERACTIVE_HOOK_ADVANCES,
    INTERACTIVE_HOOK_NODE_IDS,
)

_DATE_SUBMIT_NODES: dict[str, str] = {
    "get_filing_date": "filing_date",
    "get_last_payment_complaint": "last_payment_complaint",
    "get_last_payment_OG_creditor": "last_payment_og_creditor",
    "get_last_payment_debt_collector": "last_payment_debt_collector",
    "prelim_last_payment": "last_payment_complaint",
    "prelim_correct_payment": "last_payment_complaint",
    "prelim_open_date": "open_date",
    "prelim_breach_date": "breach_date",
    "prelim_correct_open_date": "open_date",
}

_TEXT_SUBMIT_NODES: dict[str, str] = {
    "get_plaintiff_name": "plaintiff_name",
    "get_amount_sued": "amount_sued",
    "language_primary": "primary_language",
    "mitigation_contact_uncertain": "mitigation_contact_reason",
    "mitigation_settlement_uncertain": "mitigation_settlement_reason",
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
    case_number: str | None = None
    original_creditor: str | None = None
    plaintiff_name: str | None = None
    amount_sued: str | None = None
    law_firm: str | None = None
    primary_language: str | None = None
    mitigation_contact_reason: str | None = None
    mitigation_settlement_reason: str | None = None
    open_date: date | None = None
    breach_date: date | None = None
    preliminary_fields: dict[str, PreliminaryField] = field(default_factory=dict)
    reused_answers: dict[str, str] = field(default_factory=dict)
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
    defense_answers: dict[str, str] = field(default_factory=dict)
    defense_results: dict[str, dict[str, str]] = field(default_factory=dict)
    defense_selections: dict[str, str] = field(default_factory=dict)
    checkbox_selections: dict[str, dict[str, str]] = field(default_factory=dict)
    script_facts: dict[str, str] = field(default_factory=dict)
    script_fact_sources: dict[str, str] = field(default_factory=dict)
    defense_open_questions: dict[str, dict[str, str]] = field(default_factory=dict)
    script_visited: list[str] = field(default_factory=list)
    mitigation_checkboxes: dict[str, bool] = field(default_factory=dict)
    debug_bulk_accepted: list[str] = field(default_factory=list)


def init_session(complaint_fields: dict | None = None) -> InteractiveSessionState:
    """Start a session with optional unverified, fact-only scraper input."""
    session = InteractiveSessionState()
    if complaint_fields is not None:
        load_complaint_fields(session, complaint_fields)
    return session


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
    session.defense_answers[node_id] = branch_id
    from advocate_bot_qualtrics.practice_areas.consumer_debt.tree import INTERACTIVE_TREE_DEFINITION

    definition = INTERACTIVE_TREE_DEFINITION.node_map.get(node_id)
    if definition is not None:
        if definition.fact_key and branch_id != "unknown":
            session.script_facts[definition.fact_key] = branch_id
            session.script_fact_sources[definition.fact_key] = node_id
            if definition.fact_key.startswith("answer:"):
                original = definition.fact_key.removeprefix("answer:")
                session.defense_answers[original] = branch_id
                session.reused_answers[original] = node_id
        if definition.fact_key and branch_id == "unknown" and definition.discussion_topic:
            from advocate_bot_qualtrics.practice_areas.consumer_debt.affirmative_defenses import DEFENSE_LABELS

            defense = next(key for key in DEFENSE_LABELS
                           if INTERACTIVE_TREE_DEFINITION.node(key + "_intro").discussion_topic == definition.discussion_topic)
            session.defense_open_questions[node_id] = {
                "defense": defense, "reason": definition.question, "retry_node": node_id,
            }
        for checkbox in definition.selection_checkboxes if branch_id in {"yes", "no"} else []:
            selection = "include" if branch_id == "yes" else "exclude"
            session.checkbox_selections.setdefault(checkbox.defense_id, {})[checkbox.checkbox_id] = selection
            if checkbox.checkbox_id == "main":
                session.defense_selections[checkbox.defense_id] = selection
        if branch_id != "unknown":
            # A return-to-question answer does not resolve the underlying issue.
            for key, issue in list(session.defense_open_questions.items()):
                if issue.get("retry_node") == node_id and branch_id not in {"retry", "continue"}:
                    del session.defense_open_questions[key]
    collect_preliminary_answer(session, node_id, branch_id, submitted_date, submitted_text)
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
