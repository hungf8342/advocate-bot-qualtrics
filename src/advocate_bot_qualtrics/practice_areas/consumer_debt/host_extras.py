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


def render_node(node_id: str, facts: object | None, session: InteractiveSessionState) -> CurrentNode:
    """Render approved wording with confirmed case facts and the pending question."""
    if INTERACTIVE_TREE_DEFINITION.node(node_id).discussion_topic:
        return _render_script_node(node_id, session)
    from advocate_bot_qualtrics.practice_areas.consumer_debt.affirmative_defenses import defense_summary, personalize

    source = INTERACTIVE_TREE[node_id]
    question = source.question.replace("{defense_summary}", defense_summary(session))
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
        text = personalize(session, text)
        explanation = explanation.model_copy(update={"text": text, "blocks": []})
        if explanation.show_with_question:
            question = text + "\n\n" + question
    if source.title:
        question = f"### {source.title}\n\n{question}"
    return source.model_copy(update={"question": personalize(session, question), "explanation": explanation})


def skip_collected_date_node(next_node_id: str, session: InteractiveSessionState) -> str:
    """Reuse collected PRELIM-01 fields, following only declared branch targets."""
    definition = INTERACTIVE_TREE_DEFINITION.node(next_node_id)
    if definition.selection_checkboxes:
        boxes = definition.selection_checkboxes
        choices = session.checkbox_selections.get(boxes[0].defense_id, {})
        previous_values = {choices.get(box.checkbox_id) for box in boxes}
        previous = next(iter(previous_values)) if len(previous_values) == 1 else None
        if previous is not None:
            source = next((n.id for n in INTERACTIVE_TREE_DEFINITION.nodes
                           if n.id != next_node_id and n.selection_checkboxes == boxes
                           and session.defense_answers.get(n.id) in {"yes", "no"}), None)
            if source is not None:
                branch = "yes" if previous == "include" else "no"
                target = INTERACTIVE_ROUTES[(next_node_id, branch)]
                apply_interactive_branch(session, next_node_id, branch)
                session.reused_answers[next_node_id] = source
                record = session.node_answers.get(source)
                record_node_answer(session, next_node_id, branch, record.confidence_pct if record else 0)
                return skip_collected_date_node(target, session)
    if definition.condition_key is not None:
        from advocate_bot_qualtrics.practice_areas.consumer_debt.affirmative_defenses import script_condition

        branch = script_condition(session, definition.condition_key)
        target = INTERACTIVE_ROUTES.get((next_node_id, branch))
        if target is None:
            raise ValueError(f"Condition {next_node_id!r} has no {branch!r} route")
        apply_interactive_branch(session, next_node_id, branch)
        return skip_collected_date_node(target, session)

    for node_id, source in {
        "excuse_uncredited": "common_counts_uncredited",
        "excuse_insurance": "common_counts_insurance",
    }.items():
        if next_node_id == node_id and source in session.defense_answers:
            branch = session.defense_answers[source]
            source = session.script_fact_sources.get("answer:" + source, source)
            target = INTERACTIVE_ROUTES.get((node_id, branch))
            if target is None:
                raise ValueError(f"Reused answer {branch!r} has no route from {node_id!r}")
            apply_interactive_branch(session, node_id, branch)
            session.reused_answers[node_id] = source
            record = session.node_answers.get(source)
            record_node_answer(session, node_id, branch, record.confidence_pct if record else 0)
            return skip_collected_date_node(target, session)

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
        "checkbox_selections": session.checkbox_selections,
        "defense_open_questions": session.defense_open_questions,
        "script_facts": session.script_facts,
        "script_fact_sources": session.script_fact_sources,
        "breach_date": _fmt_date(session.breach_date),
        "primary_language": session.primary_language,
        "mitigation_contact_reason": session.mitigation_contact_reason,
        "mitigation_settlement_reason": session.mitigation_settlement_reason,
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


def _script_text(text: str, session: InteractiveSessionState) -> str:
    """Substitute facts in approved script wording without evaluating defenses."""
    from advocate_bot_qualtrics.practice_areas.consumer_debt.affirmative_defenses import (
        complaint_payment, personalize,
    )

    for token, tag in (("[OPEN.DATE]", "OPEN-DATE"), ("[LAST.PAYMENT.DATE]", "LAST-PAYMENT-DATE")):
        entry = session.preliminary_fields.get(tag)
        value = entry.complaint_value if entry else None
        text = text.replace(token, value.isoformat() if isinstance(value, date) else "unknown")
    text = text.replace("[LANGUAGE]", session.primary_language or "your primary language")
    payment = complaint_payment(session)
    filing = session.filing_date
    months = f"{(filing - payment).days / 30.4375:.1f}" if filing and payment else "unknown"
    text = text.replace("[months between that payment and filing]", months)
    restatement = f"The complaint lists your last payment as {payment.isoformat()}, about {months} months before it was filed." if payment else "The last-payment date in the complaint has not been established."
    text = text.replace("{complaint_payment_restatement}", restatement)
    return personalize(session, text)


def _render_script_node(node_id: str, session: InteractiveSessionState) -> CurrentNode:
    from advocate_bot_qualtrics.core.schemas import NodeExplanation
    from advocate_bot_qualtrics.practice_areas.consumer_debt.affirmative_defenses import (
        DEFENSE_LABELS, checkbox_summary, script_condition,
    )

    definition = INTERACTIVE_TREE_DEFINITION.node(node_id)
    source = INTERACTIVE_TREE[node_id]
    defense = next(key for key, label in DEFENSE_LABELS.items()
                   if INTERACTIVE_TREE_DEFINITION.node(key + "_intro").discussion_topic == definition.discussion_topic)

    def wording(node):
        text = next((v.text for v in node.question_variants
                     if script_condition(session, v.fact_key) == v.equals), node.question)
        facts = [v.text for v in node.fact_restatements
                 if script_condition(session, v.fact_key) == v.equals]
        return _script_text("\n\n".join(part for part in [*facts, text] if part), session)

    question = wording(definition).replace("{checkbox_summary}", checkbox_summary(session, defense))
    intro = INTERACTIVE_TREE_DEFINITION.node(defense + "_intro")
    approved = _script_text(intro.explanation.text, session)
    if definition.explanation and definition.explanation.show_with_question:
        question = approved + ("\n\n" + question if question else "")
    context = [approved]
    for visited in dict.fromkeys(session.script_visited):
        node = INTERACTIVE_TREE_DEFINITION.node(visited)
        if node.discussion_topic == definition.discussion_topic:
            context.append(wording(node))
    for node in INTERACTIVE_TREE_DEFINITION.nodes:
        if node.discussion_topic != definition.discussion_topic:
            continue
        answer = session.defense_answers.get(node.id)
        if answer is not None and node.kind in {"choice", "input"}:
            branch = next((b for b in node.branches if b.id == answer), None)
            if branch:
                context.append(wording(node) + "\nRecorded answer: " + branch.label)
    context.append(question)
    if definition.title:
        question = f"### {definition.title}\n\n{question}"
    return source.model_copy(update={"question": question,
        "explanation": NodeExplanation(text="\n\n".join(dict.fromkeys(part for part in context if part)))})
