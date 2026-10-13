"""Preliminary field storage, correction provenance, and downstream reuse."""

from datetime import date

import pytest

from advocate_bot_qualtrics.core.engine import InteractiveChatEngine
from advocate_bot_qualtrics.core.schemas import ChatTurnResponse
from advocate_bot_qualtrics.practice_areas.consumer_debt.affirmative_defenses import assess_defense
from advocate_bot_qualtrics.practice_areas.consumer_debt.host_extras import skip_collected_date_node, render_node
from advocate_bot_qualtrics.practice_areas.consumer_debt.preliminary import REUSED_FIELDS, reused_branch
from advocate_bot_qualtrics.practice_areas.consumer_debt.session import init_session, apply_interactive_branch, record_node_answer
from advocate_bot_qualtrics.practice_areas.consumer_debt.tree import INTERACTIVE_TREE_DEFINITION as TREE


def answer(session, node, branch, value=None):
    apply_interactive_branch(session, node, branch,
                             submitted_date=value if isinstance(value, date) else None,
                             submitted_text=value if isinstance(value, str) else None)
    record_node_answer(session, node, branch, 90)


@pytest.mark.parametrize("creditor", ["original", "buyer"])
@pytest.mark.parametrize("filing_known", [True, False])
def test_preliminary_filing_date_drives_sol_without_being_asked_again(monkeypatch, creditor, filing_known):
    from advocate_bot_qualtrics.core import engine as engine_module

    def fake_chat(payload, node, facts, bundle):
        branch = {
            "prelim_law_firm": "submit", "get_filing_date": "submit",
            "prelim_consolidation": "no",
            "sol_payment_estimate_agree": "yes", "sol_payment_age": "unknown",
        }[node.node_id]
        return ChatTurnResponse(user_intent="answer_node", assistant_reply="Recorded.",
                                next_node_id=branch, answer_confidence_pct=100)

    monkeypatch.setattr(engine_module, "process_chat", fake_chat)
    engine = InteractiveChatEngine.from_user_input()
    engine.current_node_id = "get_filing_date"
    step = engine.submit("2026-09-24" if filing_known else "I don't know")
    assert step.error is None
    assert step.current_node_id == "verify_statement"
    entry = engine.session.preliminary_fields["FILING-DATE"]
    assert entry.value == engine.session.filing_date == (date(2026, 9, 24) if filing_known else None)
    assert entry.status == ("known" if filing_known else "unknown")
    assert entry.source_node == "get_filing_date"
    assert engine.debug_snapshot()["preliminary_fields"]["FILING-DATE"]["value"] == (
        "2026-09-24" if filing_known else None
    )

    answer(engine.session, "prelim_creditor_type", creditor)
    answer(engine.session, "prelim_oral", "yes")
    answer(engine.session, "prelim_last_payment", "submit", date(2020, 1, 1))
    engine.current_node_id = "prelim_consolidation"
    step = engine.submit("No")
    if creditor == "original":
        assert step.current_node_id == ("sol_payment_estimate_agree" if filing_known else "sol_payment_age")
        step = engine.submit("Yes" if filing_known else "I don't know")
    assert step.error is None
    assert step.current_node_id == "statute_of_limitations_decision"
    assert engine.session.defense_results["statute_of_limitations"]["status"] == "checked"
    assert sum(role == "user" and text == "2026-09-24" for role, text in engine.transcript) == int(filing_known)


def test_preliminary_filing_date_rejects_unparseable_answer(monkeypatch):
    from advocate_bot_qualtrics.core import engine as engine_module

    monkeypatch.setattr(engine_module, "process_chat", lambda *args: ChatTurnResponse(
        user_intent="answer_node", assistant_reply="Recorded.", next_node_id="submit", answer_confidence_pct=100,
    ))
    engine = InteractiveChatEngine.from_user_input()
    engine.current_node_id = "get_filing_date"
    step = engine.submit("I see a stamp but cannot read it")
    assert step.current_node_id == "get_filing_date"
    assert engine.session.filing_date is None
    assert "FILING-DATE" not in engine.session.preliminary_fields
    assert "couldn't read a date" in step.assistant_messages[0]


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


def test_litigant_payment_estimate_changes_sol_but_not_complaint_presence():
    session = init_session()
    answer(session, "prelim_creditor_type", "original")
    answer(session, "prelim_last_payment", "submit", date(2020, 1, 1))
    answer(session, "get_filing_date", "submit", date(2026, 9, 24))
    assert skip_collected_date_node("sol_creditor_type", session) == "sol_payment_estimate_agree"
    answer(session, "sol_payment_estimate_agree", "no")
    answer(session, "sol_payment_age", "yes")
    assess_defense(session, "statute_of_limitations")
    assert session.defense_results["statute_of_limitations"]["status"] == "unchecked"
    assert reused_branch(session, "cause_breach_date")[0] == "yes"
    assert session.preliminary_fields["LAST-PAYMENT-DATE"].complaint_value == date(2020, 1, 1)


def test_corrected_preliminary_payment_has_export_provenance():
    from advocate_bot_qualtrics.practice_areas.consumer_debt.field_export import build_field_confidence_rows

    session = init_session()
    answer(session, "prelim_last_payment", "submit", date(2020, 1, 1))
    answer(session, "prelim_payment_agree", "no")
    answer(session, "prelim_correct_payment", "submit", date(2025, 1, 1))
    row = next(row for row in build_field_confidence_rows(session) if row.field_key == "last_payment_complaint")
    assert row.value == date(2025, 1, 1)
    assert row.source_node_id == "prelim_correct_payment"
    assert row.corrected_from_complaint is True


def test_debug_snapshot_serializes_fields_and_disagreement():
    engine = InteractiveChatEngine.from_user_input()
    answer(engine.session, "prelim_last_payment", "submit", date(2020, 1, 1))
    answer(engine.session, "prelim_payment_agree", "no")
    answer(engine.session, "prelim_correct_payment", "submit", date(2025, 1, 1))
    field = engine.debug_snapshot()["preliminary_fields"]["LAST-PAYMENT-DATE"]
    assert field["value"] == "2025-01-01"
    assert field["complaint_value"] == "2020-01-01"
    assert field["disputed"] is True


def test_debt_buyer_preserves_without_collecting_another_payment_date():
    session = init_session()
    answer(session, "prelim_creditor_type", "buyer")
    answer(session, "prelim_last_payment", "submit", date(2010, 1, 1))
    assert skip_collected_date_node("sol_creditor_type", session) == "statute_of_limitations_result"
    assess_defense(session, "statute_of_limitations")
    assert session.defense_results["statute_of_limitations"]["status"] == "checked"
    assert session.preliminary_fields["LAST-PAYMENT-DATE"].value == date(2010, 1, 1)


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
        branch, _ = reused_branch(session, node)
        assert TREE.route(node, branch) is not None
    assert session.preliminary_fields["CONSOLIDATION"].value == "yes"
    assert "mitigation_consolidation" not in TREE.node_map


def test_real_engine_reuses_fields_after_hooks_but_waits_for_litigant_choice():
    engine = InteractiveChatEngine.from_user_input()
    answer(engine.session, "prelim_creditor_type", "buyer")
    answer(engine.session, "prelim_recognize", "yes")
    answer(engine.session, "prelim_suit_type", "breach")
    engine.current_node_id = "standing_privity_intro"
    engine._drain_hooks()
    assert "standing_privity" in engine.session.defense_results
    assert engine.current_node_id == "standing_privity_decision"
    assert engine.session.defense_selections == {}
    engine.current_node_id = "identity_theft_intro"
    engine._drain_hooks()
    assert engine.current_node_id == "identity_theft_decision"
    assert engine.session.defense_results["identity_theft"]["status"] == "unchecked"
    assert "wrong_party" not in engine.session.defense_results
    engine.reset()
    assert engine.current_node_id == "verify_case_number"
    assert engine.session.preliminary_fields == {}
    assert engine.session.reused_answers == {}
    assert engine.session.defense_selections == {}
