"""Document paragraph order, question headings, and explicitly enabled debug skips."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from advocate_bot_qualtrics.core.engine import InteractiveChatEngine
from advocate_bot_qualtrics.core.schemas import ChatTurnResponse, NodeExplanation
from advocate_bot_qualtrics.practice_areas.consumer_debt.host_extras import render_node
from advocate_bot_qualtrics.practice_areas.consumer_debt.preliminary import VERIFICATION_FIELDS
from advocate_bot_qualtrics.practice_areas.consumer_debt.session import apply_interactive_branch, init_session
from advocate_bot_qualtrics.practice_areas.consumer_debt.tree import INTERACTIVE_TREE_DEFINITION as TREE


def values(name="debt-buyer"):
    path = Path(__file__).resolve().parents[1] / f"examples/complaints/{name}.json"
    return json.loads(path.read_text())


@pytest.mark.parametrize("kind,phrase", [
    ("buyer", "If you’ve made any payments"),
    ("original", "The last payment date is the date of the most recent payment"),
])
def test_last_payment_conditional_paragraph_precedes_general_instructions(kind, phrase):
    session = init_session(values())
    apply_interactive_branch(session, "prelim_creditor_type", kind)
    prompt = render_node("verify_last_payment", None, session).question
    assert prompt.startswith("### Last Payment Date\n\n")
    assert prompt.index(phrase) < prompt.index("The complaint may list it")


def test_last_payment_intake_does_not_show_an_unverified_month_calculation():
    session = init_session(values("original-creditor"))
    prompt = render_node("verify_last_payment", None, session).question
    assert "2021-03-15" in prompt
    assert "unknown months" not in prompt
    assert "months before it was filed" not in prompt


@pytest.mark.parametrize("kind,phrase", [
    ("buyer", "When the original creditor or other company sold the debt"),
    ("original", "An original creditor must state"),
])
def test_ownership_keeps_general_intro_condition_and_general_end_in_document_order(kind, phrase):
    session = init_session(values())
    apply_interactive_branch(session, "prelim_creditor_type", kind)
    prompt = render_node("verify_ownership", None, session).question
    assert prompt.index("The complaint must say") < prompt.index(phrase) < prompt.index("Do you agree")


def test_unknown_creditor_displays_both_branches_at_their_original_positions():
    prompt = render_node("verify_ownership", None, init_session(values())).question
    assert prompt.index("The complaint must say") < prompt.index("For a debt buyer:") < prompt.index("For an original creditor:")
    payment = render_node("verify_last_payment", None, init_session(values())).question
    assert payment.index("For a debt buyer:") < payment.index("For an original creditor:") < payment.index("The complaint may list")


def test_every_preliminary_node_has_a_heading_before_its_explanation():
    session = init_session(values())
    for definition in TREE.nodes:
        if definition.id == "statute_of_limitations_intro":
            break
        if definition.kind == "condition":
            continue
        assert definition.title
        rendered = render_node(definition.id, None, session)
        assert rendered.question.startswith(f"### {definition.title}\n\n")
        if rendered.explanation and rendered.explanation.show_with_question:
            assert rendered.question.index(rendered.explanation.text) > len(definition.title)


@pytest.mark.parametrize("invalid", [
    {}, {"text": ""}, {"blocks": [{"text": ""}]},
    {"text": "General", "blocks": [{"text": "Conditional"}]},
    {"blocks": [{"text": "Conditional", "creditor_type": "unknown"}]},
])
def test_explanation_schema_rejects_ambiguous_or_empty_content(invalid):
    with pytest.raises(ValidationError):
        NodeExplanation.model_validate(invalid)


@pytest.mark.parametrize("name", ["debt-buyer", "original-creditor"])
def test_debug_shortcut_accepts_parsed_fields_without_inventing_personal_answers(monkeypatch, name):
    from advocate_bot_qualtrics.core import engine as engine_module

    def unexpected_model(*args):
        pytest.fail("Debug shortcut must run without a model call")

    monkeypatch.setattr(engine_module, "process_chat", unexpected_model)
    engine = InteractiveChatEngine.from_user_input(complaint_fields=values(name), allow_debug_shortcuts=True)
    step = engine.submit(" I agree with all! ")
    assert step.error is None
    assert engine.current_node_id not in VERIFICATION_FIELDS
    assert engine.current_node_id in {"sol_payment_estimate_agree", "statute_of_limitations_decision"}
    assert engine.debug_snapshot()["debug_bulk_accepted"]
    for tag in VERIFICATION_FIELDS.values():
        assert engine.session.preliminary_fields[tag].verification == "confirmed"
    for node in ("prelim_recognize", "prelim_oral", "prelim_consolidation"):
        assert engine.session.defense_answers[node] == "unknown"
    assert all(record.skipped and record.confidence_pct == 0 for record in engine.session.node_answers.values())


def test_debug_shortcut_preserves_existing_corrections_and_personal_answers():
    engine = InteractiveChatEngine.from_user_input(complaint_fields=values(), allow_debug_shortcuts=True)
    apply_interactive_branch(engine.session, "verify_amount", "no")
    apply_interactive_branch(engine.session, "prelim_correct_amount", "submit", submitted_text="$15")
    apply_interactive_branch(engine.session, "prelim_recognize", "no")
    engine.current_node_id = "verify_statement"
    engine.submit("I agree with all")
    assert engine.session.amount_sued == "$15"
    assert engine.session.preliminary_fields["AMOUNT"].disputed
    assert engine.session.defense_answers["prelim_recognize"] == "no"
    assert "verify_amount" not in engine.session.debug_bulk_accepted
    engine.reset()
    assert engine.allow_debug_shortcuts
    assert engine.session.debug_bulk_accepted == []


@pytest.mark.parametrize("enabled,node,message", [
    (False, "verify_case_number", "I agree with all"),
    (True, "ambiguity_decision", "I agree with all"),
    (True, "verify_case_number", "I agree with all except the amount"),
])
def test_debug_skip_is_explicit_and_limited_to_preliminary_questions(monkeypatch, enabled, node, message):
    from advocate_bot_qualtrics.core import engine as engine_module

    calls = []
    def chat(*args):
        calls.append(args)
        return ChatTurnResponse(user_intent="unclear", assistant_reply="Please answer this question.")

    monkeypatch.setattr(engine_module, "process_chat", chat)
    engine = InteractiveChatEngine.from_user_input(complaint_fields=values(), allow_debug_shortcuts=enabled)
    engine.current_node_id = node
    engine.submit(message)
    assert len(calls) == 1
    assert engine.current_node_id == node
    assert engine.session.debug_bulk_accepted == []
