"""Tests for loading fixture JSON."""

from advocate_bot_qualtrics.fact_sheet_io import DEFAULT_FIXTURE, load_complaint_fact_sheet


def test_load_sample_fixture():
    facts = load_complaint_fact_sheet(DEFAULT_FIXTURE)
    assert facts.defendant_names == ["JESSIE HINTON"]
    assert str(facts.amount_sued_for) == "953.10"
