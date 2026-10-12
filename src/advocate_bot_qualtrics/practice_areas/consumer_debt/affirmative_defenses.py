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


def preliminary_value(session: InteractiveSessionState, tag: str) -> str | date | None:
    """Read only verified or manually supplied preliminary facts."""
    entry = session.preliminary_fields.get(tag)
    return entry.value if entry and entry.status == "known" else None


def complaint_payment(session: InteractiveSessionState) -> date | None:
    """The complaint's allegation is separate from the litigant's payment estimate."""
    entry = session.preliminary_fields.get("LAST-PAYMENT-DATE")
    if entry is None:
        return session.last_payment_complaint
    if entry.verification in {"pending", "unknown"}:
        return None
    value = entry.complaint_value
    return value if isinstance(value, date) and entry.complaint_status == "present" else None


def payment_comparison_branch(session: InteractiveSessionState) -> str:
    if complaint_payment(session) is not None and session.filing_date is not None:
        return "present"
    entry = session.preliminary_fields.get("LAST-PAYMENT-DATE")
    if entry and entry.complaint_status == "missing" and entry.verification not in {"pending", "unknown"}:
        return "missing"
    return "unknown"


def personalize(session: InteractiveSessionState, text: str) -> str:
    for token, tag, fallback in (
        ("[PLAINTIFF]", "PLAINTIFF-NAME", "the plaintiff"),
        ("[ORIGINAL.CREDITOR]", "ORIGINAL.CREDITOR", "the original creditor"),
    ):
        text = text.replace(token, str(preliminary_value(session, tag) or fallback))
    return text


def defense_facts(session: InteractiveSessionState, defense: str) -> str:
    """Restate known facts after the general explanation, in document order."""
    kind = preliminary_value(session, "PLAINTIFF")
    if defense == "standing_privity" and kind == "original":
        ownership = preliminary_value(session, "OWNERSHIP")
        if ownership in {"yes", "no"}:
            verb = "stated" if ownership == "yes" else "failed to state"
            return f"In the complaint, [PLAINTIFF] {verb} it is the legal owner of the debt and has the right to bring a case to collect debt."
    if defense == "failure_to_state_cause":
        lines = []
        if preliminary_value(session, "OWNERSHIP") == "yes":
            lines.append("The complaint states that [PLAINTIFF] owns the debt.")
        labels = {"STATEMENT": "a final account statement", "OWNERSHIP.PROOF": "documents supporting ownership",
                  "OPEN-DATE": "an account opening date", "LAST-PAYMENT-DATE": "a last payment date"}
        for tag, label in labels.items():
            entry = session.preliminary_fields.get(tag)
            if not entry or entry.verification in {"pending", "unknown"}:
                continue
            present = entry.complaint_status == "present" if tag.endswith("DATE") else entry.value == "yes"
            if present:
                lines.append(f"The complaint includes {label}.")
        if kind == "buyer":
            lines.append("Debt buyers must attach their debt transfer contract with [ORIGINAL.CREDITOR] or another company, or provide a final account statement with a charge-off date from [ORIGINAL.CREDITOR].")
        return "\n\n".join(lines)
    if defense in {"identity_theft", "wrong_party"}:
        recognized = preliminary_value(session, "RECOGNIZE")
        return {
            "yes": "You’ve indicated that you recognize the account being sued for.",
            "no": "You’ve indicated that you do not recognize the account being sued for.",
        }.get(recognized, "You’ve indicated that you’re not sure whether you recognize the account being sued for.")
    if defense == "fraud" and session.defense_answers.get("identity_suspected") == "yes":
        return "You indicated earlier that you suspect identity theft—someone else opened this account under your name without your consent."
    return ""


def _sol(session: InteractiveSessionState) -> tuple[bool | None, str]:
    answers = session.defense_answers
    kind = answers.get("sol_creditor_type")
    if kind == "buyer":
        return True, "But because debt buyers often don't have records of a last payment to the original creditor, statute of limitations still often works as a defense. Litigants often check off this to preserve it, even if their last payment doesn't fall outside the specific state's rule."
    if kind != "original":
        return None, "Clinic review needed: determine whether the plaintiff is the original creditor or a debt buyer."
    age = answers.get("sol_payment_age")
    if age is not None:
        # The question asks whether payment was LESS than a year before filing.
        value = age in {"no", "unknown"}
    elif answers.get("sol_payment_estimate_agree") == "yes":
        payment, filing = complaint_payment(session), session.filing_date
        if payment is None or filing is None or payment > filing:
            return None, "Clinic review needed: confirm the complaint filing date and last payment date; the payment must not be after filing."
        value = payment <= calendar_cutoff(filing, 1)
    else:
        return None, "Clinic review needed: confirm whether the last payment was less than a year before filing."
    if value:
        return True, "Original creditors have records on when your last payment to them was. But if litigants think there’s even a small chance that their last payment was a year or more before the complaint was filed, they still often check this off to preserve the defense. You’ve indicated your last payment could be a year or more before the complaint was filed."
    return False, "This defense does not apply if you’re certain your last payment to [PLAINTIFF] was less than one year before the complaint was filed."


def _cause(session: InteractiveSessionState) -> tuple[bool | None, str]:
    answers = session.defense_answers
    answer = lambda node, trigger="yes": _answer(session, node, trigger)
    kind = answers.get("cause_creditor_type")
    proof_reason = "This defense may not apply since [PLAINTIFF] provided the required proof that they own the debt."
    if kind == "original":
        fields = {"cause_original_owner": "documents supporting ownership", "cause_open_date": "the account opening date", "cause_breach_date": "the last payment date"}
        missing = [label for node, label in fields.items() if answers.get(node) == "no"]
        if missing:
            return True, "Since the complaint does not include " + ", ".join(missing) + ", this defense may apply. Many litigants in this situation check this defense."
        if any(answers.get(node) not in {"yes", "no"} for node in fields):
            return None, "Clinic review needed: confirm the ownership documents, account opening date, and last payment date listed in the complaint."
        return False, proof_reason
    if kind == "buyer":
        attached = _any([answer("cause_statement"), answer("cause_purchase_documents")])
        if attached is False:
            return True, "This defense may apply since [PLAINTIFF] did not appear to attach either of the documents. Many litigants in this situation check this defense."
        breach = answer("cause_breach_contract")
        missing_dates = _any([answer("cause_open_date", "no"), answer("cause_breach_date", "no")])
        if breach is True and missing_dates is True:
            return True, "This defense may apply since [PLAINTIFF] did not provide the opening date of the account with [ORIGINAL.CREDITOR] or the last payment date. Many litigants in this situation check this defense."
        if attached is True and (breach is False or (breach is True and missing_dates is False)):
            return False, proof_reason
    return None, "Clinic review needed: confirm the plaintiff type, qualifying attachments, claim type, and dates listed in the complaint."


def _referral(session: InteractiveSessionState, defense: str) -> tuple[bool | None, str]:
    identity = defense == "identity_theft"
    recognized = session.defense_answers.get("identity_recognize" if identity else "wrong_party_recognize")
    suspected = session.defense_answers.get("identity_suspected" if identity else "wrong_party_owner")
    if recognized == "yes":
        return False, "This defense does not apply if you recognize the account sued for as yours."
    if recognized == "no" and suspected == "no":
        return False, ("You’ve indicated that you don’t think someone stole your identity to create this debt. This defense does not apply." if identity else "You’ve indicated that you opened this account. This defense does not apply.")
    if recognized == "no" and suspected == "yes":
        return None, ("You’ve indicated that you think someone stole your identity to create this debt. This is a serious matter which may require reporting to the FTC. Please raise your hand and notify clinic staff, who can help you file a report." if identity else "You’ve indicated that you’re not responsible for this debt because someone else opened the account. This is an important matter which may require further steps. Please raise your hand and notify clinic staff.")
    reason = ("You’re not sure whether someone stole your identity to create this debt." if identity and recognized == "no" else
              "You’re not sure whether someone else opened the account." if recognized == "no" else
              "You’re not sure whether you recognize this account as one you opened.")
    help_node = "identity_help" if identity else "wrong_party_help"
    if session.defense_answers.get(help_node) == "yes":
        reason += " Please raise your hand and ask clinic staff for help."
    return None, reason + " This defense remains unresolved for clinic review; you may continue."


def assess_defense(session: InteractiveSessionState, defense: str) -> str:
    """Record checked, unchecked, or unresolved, then let YAML advance."""
    label = DEFENSE_LABELS[defense]
    answers = session.defense_answers
    answer = lambda node, trigger="yes": _answer(session, node, trigger)
    reason = ""
    simple = {
        "unconscionable_contract", "rescission",
        "accord_satisfaction", "excuse_breach", "waiver", "oral_modification", "tender_payment",
    }
    if defense == "statute_of_limitations":
        value, reason = _sol(session)
    elif defense in simple:
        value = answer(defense)
    elif defense in {"ambiguity", "mistake"}:
        value = answer(defense)
        condition = ("you are confused about the suit, the amount sued for, or the charges" if defense == "ambiguity"
                     else "you reported an error or confusion about the amount sued for")
        if value is not None:
            reason = (f"This defense may apply since {condition}. Many litigants check off this defense, since it is a broad defense."
                      if value else "This defense may not apply based on your answer to this question.")
    elif defense == "standing_privity":
        kind = answers.get("standing_creditor_type")
        value = True if kind == "buyer" else answer("standing_claim", "no") if kind == "original" else None
        if kind == "buyer":
            reason = "Compared to original creditors like [ORIGINAL.CREDITOR], debt buyers like [PLAINTIFF] have more difficulty producing paperwork that proves they are legal owners of debt. Many litigants sued by debt buyers check this defense to preserve it."
        elif value is True:
            reason = "This defense may apply since [PLAINTIFF] does not appear to state it owns your debt. Many litigants in this situation check this defense."
        elif value is False:
            reason = "This defense does not apply since [PLAINTIFF] has stated it actually owns the debt."
    elif defense == "failure_to_state_cause":
        value, reason = _cause(session)
    elif defense in {"identity_theft", "wrong_party"}:
        value, reason = _referral(session, defense)
    elif defense == "laches":
        value = _any([answer(node) for node in ("laches", "laches_statements", "laches_lost_info")])
        if value is not None:
            reason = ("Laches may be applicable since waiting to sue made it more difficult for you to find information about your account. Many litigants check off laches, since it is a broad defense."
                      if value else "Laches may not be applicable if you did not experience difficulty in finding account information.")
    elif defense == "fraud":
        identity = answers.get("identity_suspected") == "yes" or answers.get("fraud_identity") == "yes"
        value = True if identity else answer("fraud_hidden_facts")
        if identity:
            reason = "This defense may apply since you suspect identity theft. Many litigants who check off identity theft also check off this defense."
        elif value is not None:
            parties = "[PLAINTIFF] or [ORIGINAL.CREDITOR]" if preliminary_value(session, "PLAINTIFF") == "buyer" else "[PLAINTIFF]"
            reason = (f"This defense may apply if you think {parties} hid important facts about your account from you."
                      if value else f"This defense does not apply since you indicated that {parties} did not hide important facts about your account from you.")
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
    reason = personalize(session, reason)
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
