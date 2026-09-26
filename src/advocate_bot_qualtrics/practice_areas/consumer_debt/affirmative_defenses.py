"""Deterministic screening from AFF-01 and the user's routing clarifications.

These rules implement the supplied clinic workflow, not independent legal analysis.
The YAML owns question order and routing; action handlers record defense outcomes.
"""

from __future__ import annotations

from datetime import date

from advocate_bot_qualtrics.practice_areas.consumer_debt.session import InteractiveSessionState


DEFENSE_LABELS = {
    "statute_of_limitations": "Statute of limitations",
    "ambiguity": "Ambiguity",
    "standing_privity": "Standing/privity",
    "failure_to_state_cause": "Failure to State a Cause of Action",
    "mistake": "Mistake",
    "identity_theft": "Identity Theft",
    "wrong_party": "Wrong Party",
    "laches": "Laches",
    "fraud": "Fraud, Misrepresentation, Concealment",
    "failure_to_mitigate": "Failure to mitigate",
    "common_counts": "Common Counts Only",
    "unconscionable_contract": "Unconscionable Contract",
    "rescission": "Recission",
    "lack_of_consideration": "Lack of Consideration",
    "accord_satisfaction": "Accord and Satisfaction",
    "excuse_breach": "Excuse/Breach of Contract",
    "capacity": "Capacity",
    "waiver": "Waiver",
    "oral_modification": "Oral Modification",
    "tender_payment": "Tender of Payment",
    "language_1632": "Violation of Civil Code Section 1632 Regarding Language",
}


def calendar_cutoff(filing: date, years: int) -> date:
    """Subtract calendar years, mapping a leap-day cutoff to February 28."""
    try:
        return filing.replace(year=filing.year - years)
    except ValueError:
        return filing.replace(year=filing.year - years, day=28)


def _answer(session: InteractiveSessionState, node: str, trigger: str = "yes") -> bool | None:
    answer = session.defense_answers.get(node, "unknown")
    return None if answer == "unknown" else answer == trigger


def _any(values: list[bool | None]) -> bool | None:
    if True in values:
        return True
    return None if None in values else False


def _all(values: list[bool | None]) -> bool | None:
    if False in values:
        return False
    return None if None in values else True


def _sol(session: InteractiveSessionState) -> tuple[bool | None, str]:
    answers = session.defense_answers
    creditor = answers.get("sol_creditor_type")
    if creditor == "buyer" and answers.get("sol_buyer_payment") == "no":
        return True, "Preserve this defense because no payment was made to the debt buyer, per the clinic draft."
    if creditor not in {"original", "buyer"}:
        return None, "Clinic review needed: determine whether the plaintiff is the original creditor or a debt buyer."
    if creditor == "buyer" and answers.get("sol_buyer_payment") != "yes":
        return None, "Clinic review needed: determine whether a payment was made to the debt buyer."
    filing = session.filing_date
    payment = session.last_payment_debt_collector if creditor == "buyer" else session.last_payment_complaint
    if filing is None or payment is None:
        return None, "Clinic review needed: confirm the complaint filing date and last payment date."
    if payment > filing:
        return None, "Clinic review needed: the supplied last payment date is after the complaint filing date."
    # Every specified period is at least two years. Equality is not 'before'.
    if payment >= calendar_cutoff(filing, 2):
        return False, "The last payment was not before the two-year cutoff measured from filing."
    contract = answers.get("sol_contract")
    if contract == "oral":
        years = 2
    elif contract == "written":
        years = {"ca": 4, "de": 3}.get(answers.get("sol_state_law"))
        if years is None:
            return None, "Clinic staff must read the credit card agreement to determine the applicable state law and cutoff."
    else:
        return None, "Clinic review needed: determine whether the agreement was oral or written and, if written, the applicable state law."
    cutoff = calendar_cutoff(filing, years)
    checked = payment < cutoff
    return checked, (
        f"Last payment {payment.isoformat()} is {'before' if checked else 'not before'} "
        f"the {years}-year cutoff {cutoff.isoformat()}, measured from filing {filing.isoformat()}."
    )


def assess_defense(session: InteractiveSessionState, defense: str) -> str:
    """Record checked, unchecked, or unresolved, then let YAML advance."""
    label = DEFENSE_LABELS[defense]
    answers = session.defense_answers
    answer = lambda node, trigger="yes": _answer(session, node, trigger)
    reason = ""
    simple = {
        "ambiguity", "mistake", "laches", "unconscionable_contract", "rescission",
        "accord_satisfaction", "excuse_breach", "waiver", "oral_modification", "tender_payment",
    }
    if defense == "statute_of_limitations":
        value, reason = _sol(session)
    elif defense in simple:
        value = answer(defense)
    elif defense == "standing_privity":
        kind = answers.get("standing_creditor_type")
        value = True if kind == "buyer" else (
            _any([answer("standing_claim", "no"), answer("standing_agreement", "no")])
            if kind == "original" else None
        )
    elif defense == "failure_to_state_cause":
        kind = answers.get("cause_creditor_type")
        if kind == "original":
            value = _any([answer(node, "no") for node in (
                "cause_original_owner", "cause_open_date", "cause_breach_date"
            )])
        elif kind == "buyer":
            conditions = [answer(node, "no") for node in (
                "cause_statement", "cause_purchase_claim", "cause_purchase_documents"
            )]
            breach = answer("cause_breach_contract")
            if breach is True:
                conditions += [answer("cause_open_date", "no"), answer("cause_breach_date", "no")]
            elif breach is None:
                conditions.append(None)
            value = _any(conditions)
        else:
            value = None
    elif defense in {"identity_theft", "wrong_party"}:
        prefix = "identity" if defense == "identity_theft" else "wrong_party"
        recognized = answer(prefix + "_recognize")
        suspected = answer("identity_suspected" if defense == "identity_theft" else "wrong_party_owner")
        value = False if recognized is True or (recognized is False and suspected is False) else None
        if value is None:
            reason = "Clinic review needed; leave this defense unresolved and continue."
            if defense == "identity_theft" and suspected is True:
                reason += " The draft flags suspected identity theft as a serious allegation that may require FTC reporting."
    elif defense == "fraud":
        value = _any([answer("fraud_identity"), answer("fraud_hidden_facts")])
    elif defense == "failure_to_mitigate":
        # These two nested boxes have explicit, different uncertainty rules.
        no_contact = answers.get("mitigation_contact") in {"no", "unknown"}
        refused_offer = answers.get("mitigation_settlement") == "yes"
        session.mitigation_checkboxes = {
            "no_pre_suit_contact": no_contact,
            "declined_settlement_offer": refused_offer,
        }
        value = no_contact or refused_offer
        reason = (
            f"No pre-suit contact: {'checked' if no_contact else 'unchecked'}; "
            f"declined settlement offer: {'checked' if refused_offer else 'unchecked'}."
        )
    elif defense == "common_counts":
        applicable = answer("common_counts_claim")
        value = answer("common_counts_reasons") if applicable is True else applicable
        if applicable is False:
            reason = "Not applicable: no common-count claim was reported."
    elif defense == "lack_of_consideration":
        value = _any([answer("consideration_identity"), answer("consideration_used_card", "no")])
    elif defense == "capacity":
        incapacity = _all([answer("capacity_incapacitated"), answer("capacity_disclosure")])
        value = _any([answer("capacity_minor"), incapacity])
    elif defense == "language_1632":
        value = _all([answer(node) for node in (
            "language_primary", "language_negotiation", "language_contract"
        )])
    else:
        raise ValueError(f"No assessment handler for {defense}")
    status = "unresolved" if value is None else "checked" if value else "unchecked"
    if not reason:
        reason = (
            "Confirm the unanswered or uncertain questions with clinic staff."
            if value is None else "Based on your answers to this subsection."
        )
    session.defense_results[defense] = {"status": status, "reason": reason}
    return f"{label}: {status}. {reason}"


def defense_summary(session: InteractiveSessionState) -> str:
    lines = ["Defense checklist:"]
    for defense, result in session.defense_results.items():
        lines.append(f"- {DEFENSE_LABELS[defense]}: {result['status']} — {result['reason']}")
    lines.append("\nOpen questions / clinic review:")
    unresolved = [
        f"- {DEFENSE_LABELS[key]}: {result['reason']}"
        for key, result in session.defense_results.items()
        if result["status"] == "unresolved"
    ]
    lines.extend(unresolved or ["None recorded."])
    return "\n".join(lines)
