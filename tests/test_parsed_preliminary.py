"""Parsed complaint facts require verification before downstream reuse."""

import json
from datetime import date
from pathlib import Path

import pytest

from advocate_bot_qualtrics.core.engine import InteractiveChatEngine
from advocate_bot_qualtrics.core.schemas import ChatTurnResponse
from advocate_bot_qualtrics.practice_areas.consumer_debt.host_extras import render_node
from advocate_bot_qualtrics.practice_areas.consumer_debt.preliminary import PARSED_FIELDS, reused_branch
from advocate_bot_qualtrics.practice_areas.consumer_debt.session import init_session, apply_interactive_branch
from advocate_bot_qualtrics.practice_areas.consumer_debt.tree import INTERACTIVE_TREE_DEFINITION as TREE

ROOT = Path(__file__).resolve().parents[1]


def complaint(name="original-creditor"):
    return json.loads((ROOT / f"examples/complaints/{name}.json").read_text())


@pytest.fixture
def deterministic_chat(monkeypatch):
    from advocate_bot_qualtrics.core import engine as engine_module

    def chat(payload, node, facts, bundle):
        definition = bundle.tree.node(node.node_id)
        branch = "submit" if definition.kind == "input" else payload.rsplit("User: ", 1)[1]
        return ChatTurnResponse(user_intent="answer_node", assistant_reply="Recorded.",
                                next_node_id=branch, answer_confidence_pct=100)

    monkeypatch.setattr(engine_module, "process_chat", chat)


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


def test_every_main_preliminary_question_displays_approved_explanation():
    session = init_session(complaint())
    nodes = [node for _, node in PARSED_FIELDS.values()] + [
        "prelim_recognize", "prelim_oral", "prelim_consolidation",
    ]
    for node in nodes:
        definition = TREE.node(node)
        rendered = render_node(node, None, session)
        assert definition.explanation.show_with_question
        assert rendered.explanation.text in rendered.question
        assert "{parsed_value}" not in rendered.question
        if node.startswith("verify_"):
            assert "Do you agree with this value?" in rendered.question
            assert {b.id for b in definition.branches} == {"yes", "no", "unknown"}


@pytest.mark.parametrize("name", ["original-creditor", "debt-buyer"])
def test_real_engine_verifies_all_applicable_fields_before_defenses(name, deterministic_chat):
    engine = InteractiveChatEngine.from_user_input(complaint_fields=complaint(name))
    first = engine.initial_messages()[0]
    assert complaint(name)["CASE.NUMBER"] in first
    visited = []
    for _ in range(len(TREE.nodes)):
        node = engine.current_node_id
        if node in {"sol_payment_estimate_agree", "sol_payment_age", "statute_of_limitations_decision", "sol_checkboxes_first_third"}:
            break
        visited.append(node)
        branch = "no" if node in {"prelim_oral", "prelim_consolidation"} else "yes"
        step = engine.submit(branch)
        assert step.error is None
    else:
        pytest.fail("Preliminary traversal failed to reach defense questions")
    expected = {node for _, node in PARSED_FIELDS.values()}
    if name == "original-creditor":
        expected.remove("verify_original_creditor")
    assert expected <= set(visited)
    assert engine.session.filing_date == date.fromisoformat(complaint(name)["COMPLAINT.DATE"])
    if name == "debt-buyer":
        assert "prelim_payment_agree" not in visited
        assert "prelim_open_agree" not in visited
        assert engine.session.preliminary_fields["LAST-PAYMENT-DATE"].status == "missing"
        assert reused_branch(engine.session, "cause_breach_date")[0] == "no"
    else:
        assert not {"prelim_amount_agree", "prelim_payment_agree", "prelim_open_agree"} & set(visited)
        assert "verify_original_creditor" not in visited


def test_single_agreement_question_preserves_parsed_date_when_user_disagrees(deterministic_chat):
    engine = InteractiveChatEngine.from_user_input(complaint_fields=complaint())
    engine.current_node_id = "verify_last_payment"
    assert engine.submit("no").current_node_id == "prelim_correct_payment"
    assert engine.session.last_payment_complaint is None
    assert engine.submit("2023-05-04").current_node_id == "verify_open_date"
    entry = engine.session.preliminary_fields["LAST-PAYMENT-DATE"]
    assert entry.verification == "corrected"
    assert entry.parsed_value == date(2021, 3, 15)
    assert entry.complaint_value == date(2021, 3, 15)
    assert entry.value == engine.session.last_payment_complaint == date(2023, 5, 4)
    assert entry.disputed
    assert reused_branch(engine.session, "cause_breach_date")[0] == "yes"


def test_preferred_filing_date_replaces_effective_date_and_keeps_export_provenance(deterministic_chat):
    from advocate_bot_qualtrics.practice_areas.consumer_debt.field_export import build_field_confidence_rows

    engine = InteractiveChatEngine.from_user_input(complaint_fields=complaint())
    engine.current_node_id = "verify_filing_date"
    assert engine.submit("no").current_node_id == "get_filing_date"
    assert engine.submit("2026-09-25").current_node_id == "verify_breach_date"
    entry = engine.session.preliminary_fields["FILING-DATE"]
    assert engine.session.filing_date == date(2026, 9, 25)
    assert entry.complaint_value == date(2026, 9, 30)
    row = next(row for row in build_field_confidence_rows(engine.session) if row.field_key == "filing_date")
    assert row.source_node_id == "get_filing_date"
    assert row.corrected_from_complaint


def test_unknown_verification_does_not_become_a_negative_ownership_answer(deterministic_chat):
    engine = InteractiveChatEngine.from_user_input(complaint_fields=complaint())
    engine.current_node_id = "verify_ownership"
    step = engine.submit("I don't know")
    assert step.current_node_id == "verify_last_payment"
    assert reused_branch(engine.session, "standing_claim")[0] == "unknown"
    assert engine.session.preliminary_fields["OWNERSHIP"].complaint_value == "yes"


def test_statement_and_ownership_proof_are_separate_from_ownership_claim():
    session = init_session(complaint("debt-buyer"))
    for node in ("verify_ownership", "verify_ownership_proof", "verify_statement"):
        apply_interactive_branch(session, node, "yes")
    assert session.preliminary_fields["OWNERSHIP"].value == "yes"
    assert reused_branch(session, "cause_purchase_documents")[0] == "no"
    assert reused_branch(session, "cause_statement")[0] == "no"


def test_conditional_explanations_use_confirmed_type_and_names():
    session = init_session(complaint("debt-buyer"))
    for node in ("verify_plaintiff", "verify_creditor_type", "verify_original_creditor"):
        apply_interactive_branch(session, node, "yes")
    node = render_node("verify_ownership_proof", None, session)
    assert "Example Cedar Receivables LLC" in node.question
    assert "Example Valley Card Bank" in node.question
    assert "connecting your account to the original creditor" not in node.question
    assert "[PLAINTIFF]" not in node.question


def test_reset_restores_unverified_original_input_without_mutating_caller(deterministic_chat):
    values = complaint()
    engine = InteractiveChatEngine.from_user_input(complaint_fields=values)
    values["CASE.NUMBER"] = "changed externally"
    engine.submit("yes")
    engine.reset()
    assert engine.current_node_id == "verify_case_number"
    assert engine.session.preliminary_fields["CASE.NUMBER"].verification == "pending"
    assert engine.session.preliminary_fields["CASE.NUMBER"].complaint_value == "26CV-FICTION-001"


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
