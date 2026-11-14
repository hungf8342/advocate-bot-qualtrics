"""Preliminary field storage, correction provenance, and downstream reuse."""

from datetime import date

import pytest

from advocate_bot_qualtrics.practice_areas.consumer_debt.preliminary import REUSED_FIELDS, reused_branch
from advocate_bot_qualtrics.practice_areas.consumer_debt.session import init_session, apply_interactive_branch
from advocate_bot_qualtrics.practice_areas.consumer_debt.base_tree import BASE_TREE_DEFINITION as TREE


def answer(session, node, branch, value=None):
    apply_interactive_branch(session, node, branch,
                             submitted_date=value if isinstance(value, date) else None,
                             submitted_text=value if isinstance(value, str) else None)


@pytest.mark.parametrize("original,agree,correction,tag,attr,first,corrected", [
    ("get_amount_sued", "prelim_amount_agree", "prelim_correct_amount", "AMOUNT", "amount_sued", "$5,000", "$200"),
    ("prelim_last_payment", "prelim_payment_agree", "prelim_correct_payment", "LAST-PAYMENT-DATE", "last_payment_complaint", date(2020, 1, 1), date(2025, 1, 1)),
    ("prelim_open_date", "prelim_open_agree", "prelim_correct_open_date", "OPEN-DATE", "open_date", date(2010, 1, 1), date(2012, 1, 1)),
])
def test_disagreement_replaces_effective_value_but_retains_complaint(original, agree, correction, tag, attr, first, corrected):
    session = init_session()
    answer(session, original, "submit", first)
    answer(session, agree, "no")
    assert getattr(session, attr) is None
    answer(session, correction, "submit", corrected)
    entry = session.preliminary_fields[tag]
    assert entry.value == getattr(session, attr) == corrected
    assert entry.complaint_value == first
    assert entry.complaint_status == "present"
    assert entry.disputed is True
    assert entry.source_node == correction
    assert session.preliminary_fields[tag + "-AGREEMENT"].value == "no"


def test_unknown_correction_never_reverts_to_disputed_complaint_date():
    session = init_session()
    answer(session, "prelim_last_payment", "submit", date(2020, 1, 1))
    answer(session, "prelim_payment_agree", "no")
    answer(session, "prelim_correct_payment", "no_date")
    assert session.last_payment_complaint is None
    assert reused_branch(session, "sol_payment_available")[0] == "unknown"
    assert reused_branch(session, "cause_breach_date")[0] == "yes"


@pytest.mark.parametrize("branch,expected", [("missing", "no"), ("no_date", "unknown"), ("submit", "yes")])
def test_complaint_presence_distinguishes_missing_from_unknown(branch, expected):
    session = init_session()
    for intake, reused in (("prelim_last_payment", "cause_breach_date"), ("prelim_open_date", "cause_open_date")):
        answer(session, intake, branch, date(2020, 1, 1) if branch == "submit" else None)
        assert reused_branch(session, reused)[0] == expected


@pytest.mark.parametrize("suit,breach,common", [("breach", "yes", "no"), ("common", "no", "yes"), ("both", "yes", "yes"), ("missing", "unknown", "unknown"), ("unknown", "unknown", "unknown")])
def test_suit_type_drives_documented_breach_date_condition(suit, breach, common):
    session = init_session()
    answer(session, "prelim_suit_type", suit)
    assert reused_branch(session, "cause_breach_contract")[0] == breach
    assert "common_counts_claim" not in TREE.node_map


def test_all_preliminary_fields_are_stored_and_reuse_is_valid():
    session = init_session()
    answers = {
        "get_plaintiff_name": ("submit", "Acme Bank"), "prelim_creditor_type": ("original", None),
        "prelim_recognize": ("yes", None), "prelim_law_firm": ("submit", "Example Law"),
        "get_filing_date": ("submit", date(2026, 9, 24)),
        "prelim_suit_type": ("both", None), "prelim_oral": ("no", None),
        "get_amount_sued": ("submit", "$123"), "prelim_last_payment": ("submit", date(2020, 1, 1)),
        "prelim_open_date": ("submit", date(2010, 1, 1)), "prelim_statement": ("yes", None),
        "prelim_ownership": ("no", None), "prelim_ownership_claim": ("yes", None), "prelim_verified": ("yes", None),
        "prelim_consolidation": ("yes", None),
    }
    for node, (branch, value) in answers.items():
        answer(session, node, branch, value)
    assert set(session.preliminary_fields) == {
        "PLAINTIFF-NAME", "PLAINTIFF", "RECOGNIZE", "LAW-FIRM", "FILING-DATE", "SUIT-TYPE", "ORAL", "AMOUNT",
        "LAST-PAYMENT-DATE", "OPEN-DATE", "STATEMENT", "OWNERSHIP", "OWNERSHIP.PROOF", "VERIFIED", "CONSOLIDATION",
    }
    assert session.law_firm == "Example Law"
    assert session.preliminary_fields["VERIFIED"].value == "yes"
    for node in REUSED_FIELDS:
        if node not in TREE.node_map:
            continue
        branch, _ = reused_branch(session, node)
        assert TREE.route(node, branch) is not None
    assert session.preliminary_fields["CONSOLIDATION"].value == "yes"
    assert TREE.node("mitigation_consolidation").condition_key == "field:CONSOLIDATION"
