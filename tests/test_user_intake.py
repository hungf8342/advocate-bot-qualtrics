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
    assert INTERACTIVE_START_NODE_ID == "verify_case_number"
    apply_interactive_branch(session, "sol_creditor_type", "original")
    assert session.defense_answers["sol_creditor_type"] == "original"
    assert resolve_interactive_next_node("sol_creditor_type", "original", session) == "sol_payment_available"
    assert "get_plaintiff_name" in INTERACTIVE_TREE_DEFINITION.node_map
    assert "verify_amount" in INTERACTIVE_TREE_DEFINITION.node_map


def test_user_entered_dates_drive_the_sol_session():
    session = InteractiveSessionState()
    apply_interactive_branch(session, "get_filing_date", "submit", submitted_date=date(2025, 9, 30))
    apply_interactive_branch(
        session, "prelim_last_payment", "submit", submitted_date=date(2020, 12, 23)
    )

    assert session.filing_date == date(2025, 9, 30)
    assert session.last_payment_complaint == date(2020, 12, 23)


def test_last_payment_estimate_uses_complaint_dates():
    from advocate_bot_qualtrics.practice_areas.consumer_debt.host_extras import render_node

    session = init_session()
    apply_interactive_branch(session, "get_filing_date", "submit", submitted_date=date(2026, 9, 24))
    apply_interactive_branch(session, "prelim_last_payment", "submit", submitted_date=date(2025, 9, 24))
    question = render_node("sol_payment_estimate_agree", None, session).question
    assert "12.0 months" in question
    assert "Do you agree with the last payment date in the complaint?" in question
    assert resolve_interactive_next_node("sol_payment_estimate_agree", "no") == "sol_payment_age"
