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


def test_user_intake_starts_blank_and_collects_plaintiff_and_amount():
    session = init_session()
    assert session == InteractiveSessionState()
    assert INTERACTIVE_START_NODE_ID == "get_plaintiff_name"

    apply_interactive_branch(
        session, "get_plaintiff_name", "submit", submitted_text="Acme Collections"
    )
    apply_interactive_branch(session, "get_amount_sued", "submit", submitted_text="$953.10")

    assert session.plaintiff_name == "Acme Collections"
    assert session.amount_sued == "$953.10"
    assert resolve_interactive_next_node("get_amount_sued", "submit", session) == "get_filing_date"


def test_user_entered_dates_drive_the_sol_session():
    session = InteractiveSessionState()
    apply_interactive_branch(session, "get_filing_date", "submit", submitted_date=date(2025, 9, 30))
    apply_interactive_branch(
        session, "get_last_payment_complaint", "submit", submitted_date=date(2020, 12, 23)
    )

    assert session.filing_date == date(2025, 9, 30)
    assert session.last_payment_complaint == date(2020, 12, 23)


def test_last_payment_question_includes_all_creditors_and_partial_payments():
    question = INTERACTIVE_TREE_DEFINITION.node("get_last_payment_complaint").question
    assert "original creditor or a third-party debt collector" in question
    assert "partial payments" in question
    assert resolve_interactive_next_node("get_last_payment_complaint", "submit") == "sol_computation"
