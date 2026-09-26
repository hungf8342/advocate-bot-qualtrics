from datetime import date

from advocate_bot_qualtrics.practice_areas.consumer_debt.session import (
    InteractiveSessionState,
    apply_interactive_branch,
    init_session,
)
from advocate_bot_qualtrics.practice_areas.consumer_debt.tree import (
    INTERACTIVE_START_NODE_ID,
    INTERACTIVE_TREE_DEFINITION,
    resolve_interactive_next_node,
)


def test_user_intake_starts_blank_with_preliminary_questions():
    session = init_session()
    assert session == InteractiveSessionState()
    assert INTERACTIVE_START_NODE_ID == "get_plaintiff_name"
    apply_interactive_branch(session, "sol_creditor_type", "original")
    assert session.defense_answers["sol_creditor_type"] == "original"
    assert resolve_interactive_next_node("sol_creditor_type", "original", session) == "get_filing_date"
    assert "get_plaintiff_name" in INTERACTIVE_TREE_DEFINITION.node_map
    assert "get_amount_sued" in INTERACTIVE_TREE_DEFINITION.node_map


def test_user_entered_dates_drive_the_sol_session():
    session = InteractiveSessionState()
    apply_interactive_branch(session, "get_filing_date", "submit", submitted_date=date(2025, 9, 30))
    apply_interactive_branch(
        session, "get_last_payment_complaint", "submit", submitted_date=date(2020, 12, 23)
    )

    assert session.filing_date == date(2025, 9, 30)
    assert session.last_payment_complaint == date(2020, 12, 23)


def test_last_payment_question_uses_the_selected_creditor_and_partial_payments():
    from advocate_bot_qualtrics.practice_areas.consumer_debt.host_extras import render_node

    session = init_session()
    apply_interactive_branch(session, "sol_creditor_type", "buyer")
    question = render_node("get_last_payment_complaint", None, session).question
    assert "the debt buyer" in question
    assert "partial payments" in question
    assert resolve_interactive_next_node("get_last_payment_complaint", "submit") == "sol_contract"
