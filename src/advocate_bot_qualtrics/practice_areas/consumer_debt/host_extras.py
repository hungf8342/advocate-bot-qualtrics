"""Consumer-debt host helpers: render nodes, dispute dates, debug snapshot."""

from __future__ import annotations

from datetime import date

from advocate_bot_qualtrics.core.schemas import CurrentNode
from advocate_bot_qualtrics.practice_areas.consumer_debt.fact_sheet import ComplaintFactSheet
from advocate_bot_qualtrics.practice_areas.consumer_debt.party_labels import annotate_party_terms
from advocate_bot_qualtrics.practice_areas.consumer_debt.session import (
    InteractiveSessionState,
    apply_interactive_branch,
)
from advocate_bot_qualtrics.practice_areas.consumer_debt.tree import (
    INTERACTIVE_ROUTES,
    INTERACTIVE_TREE,
    resolve_interactive_next_node,
)

_FILING_TOKEN = "{date_complaint_filed}"
_LAST_PAYMENT_TOKEN = "{date_user_failed_to_pay}"

_DATE_NODE_FIELDS: dict[str, str] = {
    "get_last_payment_OG_creditor": "last_payment_og_creditor",
    "get_last_payment_debt_collector": "last_payment_debt_collector",
}
_DISPUTE_DATE_NODES = frozenset({"get_filing_date", "get_last_payment_complaint"})

DIFFERENT_COMPLAINT_RESTART_NODES = frozenset(
    {"different_complaint_filing", "different_complaint_last_payment"}
)
RESTART_FILING_CONFIRM_MESSAGE = (
    "Let's confirm the filing date again for this complaint."
)

_HOOK_OUTCOME_KEYS = {
    "sol_computation": "sol",
    "fdcpa_computation": "fdcpa",
}


def hook_outcome_key(node_id: str) -> str | None:
    return _HOOK_OUTCOME_KEYS.get(node_id)


def _fmt_date(value: date | None) -> str:
    return value.isoformat() if value else "unknown"


def render_node(
    node_id: str,
    facts: ComplaintFactSheet,
    session: InteractiveSessionState,
) -> CurrentNode:
    source = INTERACTIVE_TREE[node_id]
    filing = session.filing_date or facts.date_complaint_filed
    last_payment = session.last_payment_complaint or facts.date_user_failed_to_pay

    question = source.question.replace(_FILING_TOKEN, _fmt_date(filing))
    question = question.replace(_LAST_PAYMENT_TOKEN, _fmt_date(last_payment))
    question = annotate_party_terms(question, facts)

    branches = [
        branch.model_copy(
            update={
                "label": annotate_party_terms(
                    branch.label.replace(_FILING_TOKEN, _fmt_date(filing)).replace(
                        _LAST_PAYMENT_TOKEN, _fmt_date(last_payment)
                    ),
                    facts,
                )
            }
        )
        for branch in source.branches
    ]
    return source.model_copy(update={"question": question, "branches": branches})


def skip_collected_date_node(next_node_id: str, session: InteractiveSessionState) -> str:
    field = _DATE_NODE_FIELDS.get(next_node_id)
    if field is None or getattr(session, field) is None:
        return next_node_id
    skip_to = INTERACTIVE_ROUTES.get((next_node_id, "submit"))
    return skip_to if skip_to else next_node_id


def consume_embedded_dispute_date(
    engine: object,
    embedded_date: date | None,
    *,
    terminal_node_id: str,
) -> None:
    """Apply a date from the user's message and skip the dispute correction node."""
    if embedded_date is None or engine.current_node_id not in _DISPUTE_DATE_NODES:
        return
    apply_interactive_branch(
        engine.session,
        engine.current_node_id,
        "submit",
        submitted_date=embedded_date,
    )
    next_id = resolve_interactive_next_node(
        engine.current_node_id, "submit", engine.session
    )
    if not next_id:
        return
    engine.current_node_id = skip_collected_date_node(next_id, engine.session)
    if engine.current_node_id == terminal_node_id:
        engine._set_tree_complete()


def build_debug_snapshot(
    *,
    session: InteractiveSessionState,
    current_node_id: str,
    tree_complete: bool,
    last_outcomes: dict[str, str],
    last_export_path: str | None,
    facts_path: str | None = None,
) -> dict:
    status = "Tree complete — ask anything" if tree_complete else "In progress"
    return {
        "facts_path": facts_path or "",
        "current_node_id": current_node_id,
        "tree_status": status,
        "filing_date": _fmt_date(session.filing_date),
        "last_payment_complaint": _fmt_date(session.last_payment_complaint),
        "last_payment_og_creditor": _fmt_date(session.last_payment_og_creditor),
        "last_payment_debt_collector": _fmt_date(session.last_payment_debt_collector),
        "filing_date_changed": session.filing_date_changed,
        "last_payment_date_changed": session.last_payment_date_changed,
        "threatened": session.threatened,
        "disclosed": session.disclosed,
        "evidence": session.evidence,
        "sol_outcome": last_outcomes.get("sol", "—"),
        "fdcpa_outcome": last_outcomes.get("fdcpa", "—"),
        "node_answers": {
            node_id: {
                "branch": record.branch_id,
                "confidence_pct": record.confidence_pct,
                "skipped": record.skipped,
            }
            for node_id, record in session.node_answers.items()
        },
        "session_fields_xlsx": last_export_path or "",
    }
