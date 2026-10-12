"""PRELIM-01 fields, corrections, and reuse of the document's bracketed tags."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from advocate_bot_qualtrics.practice_areas.consumer_debt.session import InteractiveSessionState


@dataclass
class PreliminaryField:
    value: str | date | None
    source_node: str
    status: Literal["known", "missing", "unknown"] = "known"
    complaint_value: str | date | None = None
    complaint_status: Literal["present", "missing", "unknown"] | None = None
    complaint_source: str | None = None
    disputed: bool = False
    verification: Literal["pending", "confirmed", "corrected", "unknown"] = "confirmed"
    parsed_value: str | date | None = None


# Preserve established internal tags; PARSED_FIELDS maps the new document tags.
INPUT_FIELDS = {
    "prelim_case_number": ("CASE.NUMBER", "case_number"),
    "prelim_original_creditor": ("ORIGINAL.CREDITOR", "original_creditor"),
    "get_plaintiff_name": ("PLAINTIFF-NAME", "plaintiff_name"),
    "prelim_law_firm": ("LAW-FIRM", "law_firm"),
    "get_filing_date": ("FILING-DATE", "filing_date"),
    "get_amount_sued": ("AMOUNT", "amount_sued"),
    "prelim_last_payment": ("LAST-PAYMENT-DATE", "last_payment_complaint"),
    "prelim_open_date": ("OPEN-DATE", "open_date"),
}
CHOICE_FIELDS = {
    "prelim_creditor_type": "PLAINTIFF",
    "prelim_recognize": "RECOGNIZE",
    "prelim_suit_type": "SUIT-TYPE",
    "prelim_oral": "ORAL",
    "prelim_statement": "STATEMENT",
    "prelim_ownership_claim": "OWNERSHIP",
    "prelim_ownership": "OWNERSHIP.PROOF",
    "prelim_verified": "VERIFIED",
    "prelim_consolidation": "CONSOLIDATION",
}
AGREEMENT_FIELDS = {
    "prelim_amount_agree": ("AMOUNT", "amount_sued"),
    "prelim_payment_agree": ("LAST-PAYMENT-DATE", "last_payment_complaint"),
    "prelim_open_agree": ("OPEN-DATE", "open_date"),
}
CORRECTION_FIELDS = {
    "prelim_correct_amount": ("AMOUNT", "amount_sued"),
    "prelim_correct_payment": ("LAST-PAYMENT-DATE", "last_payment_complaint"),
    "prelim_correct_open_date": ("OPEN-DATE", "open_date"),
}
COMPLAINT_FIELDS = {"AMOUNT", "LAST-PAYMENT-DATE", "OPEN-DATE"}

# Temporary scraper contract: document tags outside, established session tags inside.
PARSED_FIELDS = {
    "CASE.NUMBER": ("CASE.NUMBER", "verify_case_number"),
    "PLAINTIFF": ("PLAINTIFF-NAME", "verify_plaintiff"),
    "PLAINTIFF.TYPE": ("PLAINTIFF", "verify_creditor_type"),
    "ORIGINAL.CREDITOR": ("ORIGINAL.CREDITOR", "verify_original_creditor"),
    "LAW.FIRM": ("LAW-FIRM", "verify_law_firm"),
    "SUIT.TYPE": ("SUIT-TYPE", "verify_suit_type"),
    "AMOUNT": ("AMOUNT", "verify_amount"),
    "OWNERSHIP": ("OWNERSHIP", "verify_ownership"),
    "LAST.PAYMENT.DATE": ("LAST-PAYMENT-DATE", "verify_last_payment"),
    "OPEN.DATE": ("OPEN-DATE", "verify_open_date"),
    "COMPLAINT.DATE": ("FILING-DATE", "verify_filing_date"),
    "STATEMENT": ("STATEMENT", "verify_statement"),
    "OWNERSHIP.PROOF": ("OWNERSHIP.PROOF", "verify_ownership_proof"),
    "VERIFIED": ("VERIFIED", "verify_verified"),
}
VERIFICATION_FIELDS = {node: tag for tag, node in PARSED_FIELDS.values()}
FIELD_ATTRIBUTES = {tag: attr for tag, attr in INPUT_FIELDS.values()}
DATE_TAGS = {"LAST-PAYMENT-DATE", "OPEN-DATE", "FILING-DATE"}


def load_complaint_fields(session: InteractiveSessionState, values: dict) -> None:
    """Load fact-only parsed fields without treating them as confirmed answers.

    Null means absent from the complaint; an omitted key means not extracted.
    Invalid input is rejected before any session state changes.
    """
    if not isinstance(values, dict):
        raise ValueError("Complaint input must be a JSON object")
    unknown = set(values) - set(PARSED_FIELDS)
    if unknown:
        raise ValueError(f"Unsupported complaint fields: {', '.join(sorted(unknown))}")
    prepared = {}
    for external, (tag, _) in PARSED_FIELDS.items():
        value = values.get(external)
        presence = "unknown" if external not in values else "missing" if value is None else "present"
        if value is not None:
            if tag in DATE_TAGS:
                if not isinstance(value, str):
                    raise ValueError(f"{external} must be an ISO date string")
                value = date.fromisoformat(value)
            elif tag in {"STATEMENT", "OWNERSHIP", "OWNERSHIP.PROOF", "VERIFIED"}:
                if type(value) is not bool:
                    raise ValueError(f"{external} must be true, false, or null")
                value = "yes" if value else "no"
            elif tag in {"PLAINTIFF", "SUIT-TYPE"}:
                allowed = {"original", "buyer"} if tag == "PLAINTIFF" else {"breach", "common", "both"}
                if not isinstance(value, str) or value not in allowed:
                    raise ValueError(f"Invalid category for {external}: {value!r}")
            elif not isinstance(value, str) or not value.strip():
                raise ValueError(f"{external} must be a nonempty string or null")
            else:
                value = value.strip()
                if tag == "AMOUNT":
                    try:
                        amount = Decimal(value.replace('$', '').replace(',', ''))
                        valid = amount.is_finite() and amount > 0
                    except InvalidOperation:
                        valid = False
                    if not valid:
                        raise ValueError("AMOUNT must be a positive currency string")
        prepared[tag] = PreliminaryField(
            value=None, status="unknown", source_node="parsed_complaint",
            complaint_value=value, complaint_status=presence,
            complaint_source="parsed_complaint", parsed_value=value, verification="pending",
        )
    session.preliminary_fields.update(prepared)


def collect_preliminary_answer(
    session: InteractiveSessionState, node: str, branch: str,
    submitted_date: date | None, submitted_text: str | None,
) -> None:
    fields = session.preliminary_fields
    if node in VERIFICATION_FIELDS:
        tag = VERIFICATION_FIELDS[node]
        entry = fields.setdefault(tag, PreliminaryField(
            value=None, source_node="parsed_complaint", status="unknown",
            complaint_status="unknown", verification="pending",
        ))
        entry.value = entry.complaint_value if branch == "yes" else None
        entry.status = "unknown"
        if branch == "yes":
            entry.status = "known" if entry.value is not None else (
                "missing" if entry.complaint_status == "missing" else "unknown"
            )
        entry.verification = "confirmed" if branch == "yes" else "pending" if branch == "no" else "unknown"
        entry.disputed = branch == "no"
        entry.source_node = node
        entry.complaint_source = node
        if branch == "no" and tag == "FILING-DATE":
            session.filing_date_changed = True
        if branch == "no" and tag == "LAST-PAYMENT-DATE":
            session.last_payment_date_changed = True
        if tag in COMPLAINT_FIELDS:
            fields[tag + "-AGREEMENT"] = PreliminaryField(
                value=branch if branch != "unknown" else None,
                source_node=node, status="unknown" if branch == "unknown" else "known",
            )
        if tag in FIELD_ATTRIBUTES:
            setattr(session, FIELD_ATTRIBUTES[tag], entry.value)
        return
    if node in INPUT_FIELDS or node in CORRECTION_FIELDS:
        tag, attribute = (INPUT_FIELDS | CORRECTION_FIELDS)[node]
        value = submitted_date if submitted_date is not None else submitted_text
        if isinstance(value, str):
            value = value.strip()
        if branch != "submit":
            value = None
        status = "known" if value is not None else "missing" if branch == "missing" else "unknown"
        if node in CORRECTION_FIELDS:
            entry = fields[tag]
            entry.value, entry.status, entry.source_node = value, status, node
            entry.disputed = True
            entry.verification = "corrected"
        else:
            original = fields.get(tag)
            entry = PreliminaryField(value=value, source_node=node, status=status)
            if original is not None:
                entry.parsed_value = original.parsed_value
                entry.verification = "corrected"
                entry.disputed = original.disputed
                entry.complaint_value = original.complaint_value
                entry.complaint_status = original.complaint_status
                entry.complaint_source = original.complaint_source
            elif tag in COMPLAINT_FIELDS:
                entry.complaint_value = value
                entry.complaint_status = "present" if value is not None else status
                entry.complaint_source = node
            fields[tag] = entry
        setattr(session, attribute, value)
        if node == "prelim_correct_payment":
            session.last_payment_date_changed = True
    elif node in CHOICE_FIELDS:
        tag = CHOICE_FIELDS[node]
        original = fields.get(tag)
        fields[tag] = PreliminaryField(
            value=None if branch in {"unknown", "missing"} else branch,
            source_node=node,
            status=branch if branch in {"unknown", "missing"} else "known",
            parsed_value=original.parsed_value if original else None,
            verification="corrected" if original else "confirmed",
            complaint_value=None if branch in {"unknown", "missing"} else branch,
            complaint_status="unknown" if branch == "unknown" else "missing" if branch == "missing" else "present",
            complaint_source=node,
            disputed=original.disputed if original else False,
        )
        if original is not None:
            entry = fields[tag]
            entry.complaint_value = original.complaint_value
            entry.complaint_status = original.complaint_status
            entry.complaint_source = original.complaint_source
    elif node in AGREEMENT_FIELDS:
        tag, attribute = AGREEMENT_FIELDS[node]
        fields[tag + "-AGREEMENT"] = PreliminaryField(
            value=None if branch == "unknown" else branch,
            source_node=node, status="unknown" if branch == "unknown" else "known",
        )
        if branch != "yes":
            # Do not silently retain a disputed or unconfirmed complaint value.
            entry = fields[tag]
            entry.value, entry.status, entry.source_node = None, "unknown", node
            entry.disputed = branch == "no"
            setattr(session, attribute, None)
            if tag == "LAST-PAYMENT-DATE" and branch == "no":
                session.last_payment_date_changed = True


# Reuse traverses the same explicit YAML branches as a user answer would.
# Presence checks deliberately consult the complaint, not a corrected date.
REUSED_FIELDS = {
    "prelim_original_creditor_needed": ("PLAINTIFF", "value"),
    "sol_creditor_type": ("PLAINTIFF", "value"),
    "standing_creditor_type": ("PLAINTIFF", "value"),
    "cause_creditor_type": ("PLAINTIFF", "value"),
    "standing_claim": ("OWNERSHIP", "value"),
    "cause_original_owner": ("OWNERSHIP.PROOF", "value"),
    "cause_purchase_documents": ("OWNERSHIP.PROOF", "value"),
    "cause_statement": ("STATEMENT", "value"),
    "cause_breach_contract": ("SUIT-TYPE", "breach"),
    "common_counts_claim": ("SUIT-TYPE", "common"),
    "cause_open_date": ("OPEN-DATE", "presence"),
    "cause_breach_date": ("LAST-PAYMENT-DATE", "presence"),
    "identity_recognize": ("RECOGNIZE", "value"),
    "wrong_party_recognize": ("RECOGNIZE", "value"),
    "mitigation_consolidation": ("CONSOLIDATION", "value"),
}


def reused_branch(session: InteractiveSessionState, node: str) -> tuple[str, str] | None:
    if node == "cause_attachment_screen":
        values = [session.defense_answers.get(key) for key in ("cause_statement", "cause_purchase_documents")]
        branch = "yes" if "yes" in values else "no" if values == ["no", "no"] else "unknown"
        return branch, "cause_purchase_documents"
    if node == "sol_payment_available":
        from advocate_bot_qualtrics.practice_areas.consumer_debt.affirmative_defenses import payment_comparison_branch

        entry = session.preliminary_fields.get("LAST-PAYMENT-DATE")
        source = (entry.complaint_source or entry.source_node) if entry else "verify_last_payment"
        return payment_comparison_branch(session), source
    if node == "fraud_identity":
        # Reuse suspicion, including the skipped-question case. Never ask twice.
        return session.defense_answers.get("identity_suspected", "unknown"), "identity_suspected" if "identity_suspected" in session.defense_answers else "identity_recognize"
    binding = REUSED_FIELDS.get(node)
    if binding is None or binding[0] not in session.preliminary_fields:
        return None
    tag, mode = binding
    entry = session.preliminary_fields[tag]
    source = entry.source_node
    value = entry.value
    if mode == "presence":
        branch = "unknown"
        if entry.verification not in {"pending", "unknown"}:
            branch = {"present": "yes", "missing": "no"}.get(entry.complaint_status, "unknown")
        source = entry.complaint_source or source
    elif mode == "date":
        branch = "submit" if isinstance(value, date) else "no_date"
    elif mode == "contract":
        branch = {"yes": "oral", "no": "written"}.get(value, "unknown")
    elif mode in {"breach", "common"}:
        branch = "unknown" if entry.status != "known" else "yes" if value in {mode, "both"} else "no"
    else:
        branch = str(value) if entry.status == "known" else "unknown"
    return branch, source
