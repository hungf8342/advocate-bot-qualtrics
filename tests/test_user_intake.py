from datetime import date

from advocate_bot_qualtrics.practice_areas.consumer_debt.session import (
    InteractiveSessionState,
    apply_interactive_branch,
    init_session,
)
from advocate_bot_qualtrics.practice_areas.consumer_debt.base_tree import (
    BASE_TREE_DEFINITION,
)


def test_user_intake_starts_blank_with_preliminary_questions():
    session = init_session()
    assert session == InteractiveSessionState()
    assert BASE_TREE_DEFINITION.start_node_id == "verify_case_number"
    apply_interactive_branch(session, "sol_creditor_type", "original")
    assert session.defense_answers["sol_creditor_type"] == "original"
    assert BASE_TREE_DEFINITION.route("sol_creditor_type", "original") == "sol_payment_available"
    assert "get_plaintiff_name" in BASE_TREE_DEFINITION.node_map
    assert "verify_amount" in BASE_TREE_DEFINITION.node_map


def test_user_entered_dates_drive_the_sol_session():
    session = InteractiveSessionState()
    apply_interactive_branch(session, "get_filing_date", "submit", submitted_date=date(2025, 9, 30))
    apply_interactive_branch(
        session, "prelim_last_payment", "submit", submitted_date=date(2020, 12, 23)
    )

    assert session.filing_date == date(2025, 9, 30)
    assert session.last_payment_complaint == date(2020, 12, 23)
