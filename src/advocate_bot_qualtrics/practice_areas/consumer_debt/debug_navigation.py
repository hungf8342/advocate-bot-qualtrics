"""Explicit debug navigation without inventing answers to skipped defenses."""
from .workflow import (
    DEFENSES, PRELIMINARY_FIELDS, PRELIMINARY_SUMMARY, GuidedAnswer, ClickthroughReview,
)

# Used only to fill unanswered intake fields after an explicit debug jump.
DEBUG_ANSWERS = {
    "guided_case_number": "26CV-DEBUG-001", "guided_plaintiff": "Example Harbor Bank",
    "guided_creditor_type": "original", "guided_original_creditor": "Example Original Bank",
    "guided_law_firm": "Fictional Maple Legal Group", "guided_suit_type": "both",
    "guided_amount": "4250.00", "guided_payment_date": "2021-03-15",
    "guided_open_date": "2017-08-20", "guided_filing_date": "2026-09-30",
    "guided_breach_date": "2021-04-01", "guided_statement": "yes",
    "guided_ownership_claim": "yes", "guided_ownership_proof": "yes",
    "guided_verified": "no", "guided_consolidation": "no",
    "guided_recognize": "yes", "guided_oral": "no",
}


def jump_to_section(current: ClickthroughReview, section: str, draft_value: str | None = None,
                    *, draft_node: str | None = None) -> ClickthroughReview:
    if section not in {*DEFENSES, "preliminary"}:
        raise ValueError("Choose an implemented defense or preliminary fields.")
    # Retain confirmed intake, including fields after a Back/Change cursor.
    # Rebuild its order so changing creditor type can add/remove the name field.
    confirmed = {}
    for answer in current.history:
        if answer.node_id not in {"guided_welcome", *PRELIMINARY_FIELDS}:
            break
        confirmed[answer.node_id] = answer
    draft_node = draft_node or current.current
    if draft_value is not None:
        if draft_node not in PRELIMINARY_FIELDS:
            raise ValueError("Only a preliminary field can be submitted with a section jump.")
        confirmed[draft_node] = GuidedAnswer(node_id=draft_node, value=draft_value)
    target = ClickthroughReview(current.defaults, debug_section=section)
    for _ in range(len(PRELIMINARY_FIELDS) + 2):
        if target.current == PRELIMINARY_SUMMARY:
            break
        node = target.current
        if node in confirmed:
            answer = confirmed[node]
        else:
            if node == "guided_welcome":
                value = "continue"
            else:
                value = target._intake_page()["default_value"]
                if value is None or node == "guided_suit_type":
                    value = DEBUG_ANSWERS[node]
            answer = GuidedAnswer(node_id=node, value=str(value), automatic=True)
        target._apply_answer(answer)
        target.history.append(answer)
    else:
        raise ValueError("The debug intake could not be filled.")
    if section != "preliminary":
        answer = GuidedAnswer(node_id=PRELIMINARY_SUMMARY, value="continue", automatic=True)
        target._apply_answer(answer)
        target.history.append(answer)
    return target
