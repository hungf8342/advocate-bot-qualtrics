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
from advocate_bot_qualtrics.practice_areas.consumer_debt.preliminary import (
    reused_branch, VERIFICATION_FIELDS,
)

from advocate_bot_qualtrics.practice_areas.consumer_debt.tree import (
    INTERACTIVE_ROUTES,
    INTERACTIVE_TREE,
    INTERACTIVE_TREE_DEFINITION,
)

CHOICE_LABELS = {
    "yes": "Yes", "no": "No", "original": "Original creditor", "buyer": "Debt buyer",
    "breach": "Breach of contract", "common": "Common counts", "both": "Breach of contract and common counts",
}

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
    from advocate_bot_qualtrics.practice_areas.consumer_debt.affirmative_defenses import (
        complaint_payment, defense_facts, defense_summary, personalize, preliminary_value,
    )

    payment = complaint_payment(session)
    elapsed = (f"{(filing - payment).days / 30.4375:.1f}" if filing and payment else "unknown")
    entry = session.preliminary_fields.get("LAST-PAYMENT-DATE")
    if entry and entry.complaint_status == "present" and isinstance(entry.complaint_value, date):
        payment_restatement = f"The complaint lists the last payment date as {entry.complaint_value.isoformat()}."
    elif entry and entry.complaint_status == "missing":
        payment_restatement = "The complaint does not appear to list the last payment date."
    else:
        payment_restatement = ""
    if session.defense_answers.get("sol_payment_estimate_agree") == "no":
        payment_context = "You have indicated you disagree with how much time passed between your last payment and [PLAINTIFF] filing a complaint."
    elif session.defense_answers.get("sol_payment_available") == "missing":
        payment_context = "The complaint did not appear to include the last payment date."
    else:
        payment_context = "The time between your last payment and filing has not been confirmed."
    payment_context += " If the complaint does not give the correct last payment date, your bank records, payment confirmations, or account history may help you estimate when you last paid. Whether the last payment was less than a year before [PLAINTIFF] filed the complaint would be useful enough."

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
        "{defense_facts}": defense_facts(session, node_id.removesuffix("_intro")),
        "{payment_elapsed_months}": elapsed,
        "{complaint_payment_restatement}": payment_restatement,
        "{payment_age_context}": payment_context,
        "{fraud_parties}": "[PLAINTIFF] or [ORIGINAL.CREDITOR]" if preliminary_value(session, "PLAINTIFF") == "buyer" else "[PLAINTIFF]",
        "{identity_uncertainty}": "You’ve indicated that you’re not sure whether someone stole your identity to create this debt." if session.defense_answers.get("identity_recognize") == "no" else "You’ve indicated that you’re not sure whether you recognize this account as one you opened.",
        "{identity_help_question}": "Do you have further questions on how to determine whether this account exists because of ID theft?" if session.defense_answers.get("identity_recognize") == "no" else "Do you have further questions on how to determine whether this account belongs to you or not?",
        "{wrong_party_uncertainty}": "You’ve indicated that you’re not sure whether someone else opened the account." if session.defense_answers.get("wrong_party_recognize") == "no" else "You’ve indicated that you’re not sure whether you recognize this account as one you opened.",
    }
    for token, value in replacements.items():
        question = question.replace(token, value)
    question = personalize(session, question)
    if node_id in VERIFICATION_FIELDS:
        entry = session.preliminary_fields.get(VERIFICATION_FIELDS[node_id])
        value = entry.complaint_value if entry else None
        display = (value.isoformat() if isinstance(value, date) else
                   CHOICE_LABELS.get(str(value), str(value)) if value is not None else
                   "Not stated in the complaint" if entry and entry.complaint_status == "missing" else
                   "Not extracted / unknown")
        question = question.replace("{parsed_value}", display)
    explanation = source.explanation
    if explanation is not None:
        creditor = session.preliminary_fields.get("PLAINTIFF")
        kind = creditor.value if creditor else None
        paragraphs = []
        for block in explanation.blocks:
            if block.creditor_type is None or block.creditor_type == kind:
                paragraphs.append(block.text)
            elif kind not in {"original", "buyer"}:
                label = "a debt buyer" if block.creditor_type == "buyer" else "an original creditor"
                paragraphs.append(f"For {label}: {block.text}")
        text = "\n\n".join(paragraphs) if explanation.blocks else explanation.text
        for token, value in replacements.items():
            text = text.replace(token, value)
        for token, tag, fallback in (
            ("[PLAINTIFF]", "PLAINTIFF-NAME", "the plaintiff"),
            ("[ORIGINAL.CREDITOR]", "ORIGINAL.CREDITOR", "the original creditor"),
        ):
            entry = session.preliminary_fields.get(tag)
            text = text.replace(token, str(entry.value) if entry and entry.value else fallback)
        explanation = explanation.model_copy(update={"text": text, "blocks": []})
        if explanation.show_with_question:
            question = text + "\n\n" + question
    if source.title:
        question = f"### {source.title}\n\n{question}"
    if source.discussion_mode in {"decision", "clarification", "questions"}:
        defense = node_id.rsplit("_", 1)[0]
        context = [explanation.text if explanation else "", personalize(session, defense_facts(session, defense))]
        result = session.defense_results.get(defense)
        if result:
            context.append(result["reason"])
        # Give scoped Q&A the relevant answers even when earlier turns have
        # fallen out of the model's short transcript window. No assessment
        # statuses or unverified scraper fields are included.
        for definition in INTERACTIVE_TREE_DEFINITION.nodes:
            if (definition.discussion_topic != source.discussion_topic
                    or definition.discussion_mode != "screening" or definition.kind != "choice"):
                continue
            answer = session.defense_answers.get(definition.id)
            branch = next((b for b in definition.branches if b.id == answer), None)
            if branch is not None:
                detail = definition.question
                for token, value in replacements.items():
                    detail = detail.replace(token, value)
                context.append(personalize(session, detail) + "\nRecorded answer: " + branch.label)
        if defense == "statute_of_limitations":
            if payment:
                context.append(f"The complaint's listed last payment date is {payment.isoformat()}.")
            if filing:
                context.append(f"The confirmed complaint filing date is {filing.isoformat()}.")
        from advocate_bot_qualtrics.core.schemas import NodeExplanation

        explanation = NodeExplanation(text="\n\n".join(part for part in context if part.strip()))
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
    return source.model_copy(update={"question": question, "branches": branches, "explanation": explanation})


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


def debug_accept_preliminary(session: InteractiveSessionState, current_node_id: str) -> str | None:
    """Debug-only bulk agreement; preserve prior answers and never invent personal facts."""
    preliminary_ids = []
    for definition in INTERACTIVE_TREE_DEFINITION.nodes:
        if definition.id == "statute_of_limitations_intro":
            break
        preliminary_ids.append(definition.id)
    if current_node_id not in preliminary_ids:
        return None
    for node, tag in VERIFICATION_FIELDS.items():
        entry = session.preliminary_fields.get(tag)
        if entry is not None and (entry.verification != "pending" or entry.disputed):
            continue
        branch = "yes" if entry and entry.complaint_status != "unknown" else "unknown"
        apply_interactive_branch(session, node, branch)
        record_node_answer(session, node, branch, 0, skipped=True)
        session.debug_bulk_accepted.append(node)
    for node in ("prelim_recognize", "prelim_oral", "prelim_consolidation"):
        if node not in session.defense_answers:
            apply_interactive_branch(session, node, "unknown")
            record_node_answer(session, node, "unknown", 0, skipped=True)
    return "statute_of_limitations_intro"


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
        "defense_selections": session.defense_selections,
        "preliminary_fields": {
            tag: {key: value.isoformat() if isinstance(value, date) else value
                  for key, value in asdict(entry).items()}
            for tag, entry in session.preliminary_fields.items()
        },
        "reused_answers": session.reused_answers,
        "mitigation_checkboxes": session.mitigation_checkboxes,
        "debug_bulk_accepted": session.debug_bulk_accepted,
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
