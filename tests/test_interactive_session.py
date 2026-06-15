from datetime import date

from advocate_bot_qualtrics.decision_tree.interactive_session import (
    InteractiveSessionState,
    apply_interactive_branch,
)


def test_submit_with_none_date_does_not_overwrite_existing():
    session = InteractiveSessionState(last_payment_complaint=date(2020, 12, 23))
    apply_interactive_branch(
        session,
        "get_last_payment_complaint",
        "submit",
        submitted_date=None,
    )
    assert session.last_payment_complaint == date(2020, 12, 23)


def test_yes_with_date_on_collector_node():
    session = InteractiveSessionState()
    apply_interactive_branch(
        session,
        "additional_payment_debt_collector",
        "yes",
        submitted_date=date(2024, 1, 4),
    )
    assert session.last_payment_debt_collector == date(2024, 1, 4)


def test_filing_date_changed_on_submit():
    session = InteractiveSessionState()
    apply_interactive_branch(
        session,
        "get_filing_date",
        "submit",
        submitted_date=date(2024, 2, 1),
    )
    assert session.filing_date == date(2024, 2, 1)
    assert session.filing_date_changed is True


def test_last_payment_date_changed_on_submit():
    session = InteractiveSessionState()
    apply_interactive_branch(
        session,
        "get_last_payment_complaint",
        "submit",
        submitted_date=date(2023, 5, 15),
    )
    assert session.last_payment_complaint == date(2023, 5, 15)
    assert session.last_payment_date_changed is True


def test_record_node_answer_stores_confidence_and_skipped():
    from advocate_bot_qualtrics.decision_tree.interactive_session import record_node_answer

    session = InteractiveSessionState()
    record_node_answer(session, "confirm_filing_date", "yes", 0, skipped=True)
    record = session.node_answers["confirm_filing_date"]
    assert record.branch_id == "yes"
    assert record.confidence_pct == 0
    assert record.skipped is True
