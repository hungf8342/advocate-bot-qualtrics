"""PRELIM-01 fields, corrections, and reuse of the document's bracketed tags."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
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


# The Word document's PLAINTIFF choices identify creditor type. Keep the name too.
INPUT_FIELDS = {
    "get_plaintiff_name": ("PLAINTIFF-NAME", "plaintiff_name"),
    "prelim_law_firm": ("LAW-FIRM", "law_firm"),
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
    "prelim_ownership": "OWNERSHIP",
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


def collect_preliminary_answer(
    session: InteractiveSessionState, node: str, branch: str,
    submitted_date: date | None, submitted_text: str | None,
) -> None:
    fields = session.preliminary_fields
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
        else:
            entry = PreliminaryField(value=value, source_node=node, status=status)
            if tag in COMPLAINT_FIELDS:
                entry.complaint_value = value
                entry.complaint_status = "present" if value is not None else status
                entry.complaint_source = node
            fields[tag] = entry
        setattr(session, attribute, value)
        if node == "prelim_correct_payment":
            session.last_payment_date_changed = True
    elif node in CHOICE_FIELDS:
        fields[CHOICE_FIELDS[node]] = PreliminaryField(
            value=None if branch in {"unknown", "missing"} else branch,
            source_node=node,
            status=branch if branch in {"unknown", "missing"} else "known",
        )
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
    "sol_creditor_type": ("PLAINTIFF", "value"),
    "sol_payment_recipient": ("PLAINTIFF", "value"),
    "standing_creditor_type": ("PLAINTIFF", "value"),
    "cause_creditor_type": ("PLAINTIFF", "value"),
    "get_last_payment_complaint": ("LAST-PAYMENT-DATE", "date"),
    "sol_contract": ("ORAL", "contract"),
    "standing_agreement": ("OWNERSHIP", "value"),
    "cause_original_owner": ("OWNERSHIP", "value"),
    "cause_purchase_documents": ("OWNERSHIP", "value"),
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
    binding = REUSED_FIELDS.get(node)
    if binding is None or binding[0] not in session.preliminary_fields:
        return None
    tag, mode = binding
    entry = session.preliminary_fields[tag]
    source = entry.source_node
    value = entry.value
    if mode == "presence":
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
