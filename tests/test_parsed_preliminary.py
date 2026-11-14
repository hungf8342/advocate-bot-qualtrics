"""Parsed complaint facts require verification before downstream reuse."""

import json
from datetime import date
from pathlib import Path

import pytest

from advocate_bot_qualtrics.practice_areas.consumer_debt.preliminary import PARSED_FIELDS, reused_branch
from advocate_bot_qualtrics.practice_areas.consumer_debt.session import init_session, apply_interactive_branch

ROOT = Path(__file__).resolve().parents[1]


def complaint(name="original-creditor"):
    return json.loads((ROOT / f"examples/complaints/{name}.json").read_text())


@pytest.mark.parametrize("name", ["original-creditor", "debt-buyer"])
def test_samples_are_fact_only_and_all_values_start_unverified(name):
    values = complaint(name)
    session = init_session(values)
    assert set(values) == set(PARSED_FIELDS)
    assert session.defense_answers == session.defense_results == {}
    assert session.filing_date is None
    assert session.last_payment_complaint is None
    assert all(entry.value is None and entry.verification == "pending"
               for entry in session.preliminary_fields.values())
    assert reused_branch(session, "sol_creditor_type")[0] == "unknown"
    assert reused_branch(session, "cause_breach_date")[0] == "unknown"


def test_statement_and_ownership_proof_are_separate_from_ownership_claim():
    session = init_session(complaint("debt-buyer"))
    for node in ("verify_ownership", "verify_ownership_proof", "verify_statement"):
        apply_interactive_branch(session, node, "yes")
    assert session.preliminary_fields["OWNERSHIP"].value == "yes"
    assert reused_branch(session, "cause_purchase_documents")[0] == "no"
    assert reused_branch(session, "cause_statement")[0] == "no"


@pytest.mark.parametrize("values", [
    {"defense_results": {}}, {"RECOGNIZE": True}, {"STATEMENT": "false"},
    {"COMPLAINT.DATE": "not a date"}, {"AMOUNT": "-1"}, {"PLAINTIFF.TYPE": "yes"},
])
def test_scraper_input_rejects_nonfacts_and_invalid_values(values):
    with pytest.raises(ValueError):
        init_session(values)


def test_omitted_and_explicitly_missing_fields_are_distinct():
    session = init_session({"OPEN.DATE": None})
    assert session.preliminary_fields["OPEN-DATE"].complaint_status == "missing"
    assert session.preliminary_fields["FILING-DATE"].complaint_status == "unknown"


@pytest.mark.parametrize('value,branch,status', [('2024-03-01','submit','present'),(None,'missing','missing'),(None,'unknown','unknown')])
def test_breach_date_correction_updates_complaint_contents_and_preserves_parsed_value(value,branch,status):
    from advocate_bot_qualtrics.practice_areas.consumer_debt.affirmative_defenses import script_condition
    session=init_session({'BREACH.DATE':'2023-01-01'})
    apply_interactive_branch(session,'verify_breach_date','no')
    apply_interactive_branch(session,'prelim_breach_date',branch,
        submitted_date=date.fromisoformat(value) if value else None)
    entry=session.preliminary_fields['BREACH-DATE']
    assert entry.parsed_value==date(2023,1,1)
    assert entry.complaint_value==session.breach_date==(date.fromisoformat(value) if value else None)
    assert entry.complaint_status==status
    assert script_condition(session,'complaint:BREACH-DATE')=={'present':'yes','missing':'no','unknown':'unknown'}[status]


def test_omitted_breach_date_is_not_assumed_missing():
    from advocate_bot_qualtrics.practice_areas.consumer_debt.affirmative_defenses import script_condition
    session=init_session({})
    apply_interactive_branch(session,'verify_breach_date','yes')
    assert session.preliminary_fields['BREACH-DATE'].complaint_status=='unknown'
    assert script_condition(session,'complaint:BREACH-DATE')=='unknown'
