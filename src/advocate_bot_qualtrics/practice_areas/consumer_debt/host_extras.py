"""Consumer-debt host helpers: render nodes, dispute dates, debug snapshot."""

from __future__ import annotations

from datetime import date
from dataclasses import asdict

from advocate_bot_qualtrics.core.schemas import CurrentNode
from advocate_bot_qualtrics.practice_areas.consumer_debt.session import (
    InteractiveSessionState,
    apply_interactive_branch,
    record_node_answer,
)
from advocate_bot_qualtrics.practice_areas.consumer_debt.preliminary import reused_branch
from advocate_bot_qualtrics.practice_areas.consumer_debt.tree import (
    INTERACTIVE_ROUTES,
    INTERACTIVE_TREE,
    INTERACTIVE_TREE_DEFINITION,
)

_FILING_TOKEN = "{date_complaint_filed}"
_LAST_PAYMENT_TOKEN = "{date_user_failed_to_pay}"

_DATE_NODE_FIELDS: dict[str, str] = {
    "get_last_payment_OG_creditor": "last_payment_og_creditor",
    "get_last_payment_debt_collector": "last_payment_debt_collector",
}

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
    if node_id.endswith("_result"):
        return node_id.removesuffix("_result")
    return _HOOK_OUTCOME_KEYS.get(node_id)


def _fmt_date(value: date | None) -> str:
    return value.isoformat() if value else "unknown"


def render_node(
    node_id: str,
    facts: object | None,
    session: InteractiveSessionState,
) -> CurrentNode:
    source = INTERACTIVE_TREE[node_id]
    del facts
    filing = session.filing_date
    last_payment = session.last_payment_complaint

    question = source.question.replace(_FILING_TOKEN, _fmt_date(filing))
    question = question.replace(_LAST_PAYMENT_TOKEN, _fmt_date(last_payment))
    from advocate_bot_qualtrics.practice_areas.consumer_debt.affirmative_defenses import defense_summary

    consolidation = session.defense_answers.get("mitigation_consolidation")
    negotiation_party = (
        "you or your debt consolidation company" if consolidation == "yes"
        else "you" if consolidation == "no"
        else "you or a debt consolidation company acting for you, if any"
    )
    replacements = {
        "{payment_recipient}": "the debt buyer" if session.defense_answers.get("sol_creditor_type") == "buyer" else "the original creditor",
        "{negotiation_party}": negotiation_party,
        "{agreement_party}": negotiation_party,
        "{defense_summary}": defense_summary(session),
        "{amount_sued}": session.amount_sued or "unknown",
        "{open_date}": _fmt_date(session.open_date),
    }
    for token, value in replacements.items():
        question = question.replace(token, value)
    branches = [
        branch.model_copy(
            update={
                "label": branch.label.replace(_FILING_TOKEN, _fmt_date(filing)).replace(
                    _LAST_PAYMENT_TOKEN, _fmt_date(last_payment)
                )
            }
        )
        for branch in source.branches
    ]
    return source.model_copy(update={"question": question, "branches": branches})


def skip_collected_date_node(next_node_id: str, session: InteractiveSessionState) -> str:
    """Reuse collected PRELIM-01 fields, following only declared branch targets."""
    while (reused := reused_branch(session, next_node_id)) is not None:
        branch, source = reused
        definition = INTERACTIVE_TREE_DEFINITION.node(next_node_id)
        target = INTERACTIVE_ROUTES.get((next_node_id, branch))
        if target is None:
            raise ValueError(f"Reused field has invalid branch {branch!r} for {next_node_id!r}")
        value = session.last_payment_complaint if definition.kind == "input" else None
        apply_interactive_branch(session, next_node_id, branch, submitted_date=value)
        record = session.node_answers.get(source)
        record_node_answer(session, next_node_id, branch,
                           record.confidence_pct if record else 0,
                           skipped=record.skipped if record else False)
        session.reused_answers[next_node_id] = source
        next_node_id = target
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
    """Compatibility callback; AFF-01 collects each date in its own question.

    In particular, a filing-date answer must never fill the next payment node.
    """
    return None


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
        "defense_results": session.defense_results,
        "preliminary_fields": {
            tag: {key: value.isoformat() if isinstance(value, date) else value
                  for key, value in asdict(entry).items()}
            for tag, entry in session.preliminary_fields.items()
        },
        "reused_answers": session.reused_answers,
        "mitigation_checkboxes": session.mitigation_checkboxes,
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
