from advocate_bot_qualtrics.decision_tree.party_labels import annotate_party_terms
from advocate_bot_qualtrics.schemas.complaint_fact_sheet import ComplaintFactSheet


def test_annotate_original_creditor_and_debt_collector():
    facts = ComplaintFactSheet(
        original_creditor_name="Midgard Bank",
        debt_collector_name="Southwest Collections, Inc.",
    )
    text = (
        "Did you pay the original creditor? Did the debt collector contact you?"
    )
    out = annotate_party_terms(text, facts)
    assert "original creditor (Midgard Bank)" in out
    assert "debt collector (Southwest Collections, Inc.)" in out


def test_annotate_case_insensitive():
    facts = ComplaintFactSheet(original_creditor_name="Midgard Bank")
    out = annotate_party_terms("The Original Creditor held the account.", facts)
    assert "midgard bank" in out.lower()
    assert "original creditor" in out.lower()


def test_annotate_skips_when_name_missing():
    facts = ComplaintFactSheet()
    text = "Pay the original creditor and debt collector."
    assert annotate_party_terms(text, facts) == text


def test_annotate_skips_already_parenthesized():
    facts = ComplaintFactSheet(original_creditor_name="Midgard Bank")
    text = "The original creditor (Midgard Bank) sold the debt."
    assert annotate_party_terms(text, facts) == text


def test_annotate_does_not_double_append():
    facts = ComplaintFactSheet(original_creditor_name="Midgard Bank")
    once = annotate_party_terms("original creditor", facts)
    twice = annotate_party_terms(once, facts)
    assert twice == "original creditor (Midgard Bank)"
    assert "(Midgard Bank) (Midgard Bank)" not in twice
