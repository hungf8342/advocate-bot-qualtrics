from datetime import date

from advocate_bot_qualtrics.decision_tree.interactive_computations import (
    SOL_LIMIT_DAYS,
    run_fdcpa_computation,
    run_sol_computation,
)
from advocate_bot_qualtrics.decision_tree.interactive_session import InteractiveSessionState


def test_sol_affirmative_when_beyond_limit():
    session = InteractiveSessionState(
        filing_date=date(2025, 1, 1),
        last_payment_complaint=date(2020, 1, 1),
    )
    assert (date(2025, 1, 1) - date(2020, 1, 1)).days > SOL_LIMIT_DAYS
    assert run_sol_computation(session) == "SOL is an affirmative defense."


def test_sol_not_affirmative_within_limit():
    session = InteractiveSessionState(
        filing_date=date(2025, 1, 1),
        last_payment_complaint=date(2024, 6, 1),
    )
    assert run_sol_computation(session) == "SOL is not an affirmative defense."


def test_sol_not_affirmative_with_recent_debt_collector_payment():
    session = InteractiveSessionState(
        filing_date=date(2025, 9, 30),
        last_payment_complaint=date(2020, 12, 23),
        last_payment_debt_collector=date(2024, 9, 15),
    )
    assert run_sol_computation(session) == "SOL is not an affirmative defense."


def test_sol_insufficient_dates():
    session = InteractiveSessionState(filing_date=None)
    assert "Insufficient" in run_sol_computation(session)


def test_fdcpa_tiers():
    assert (
        run_fdcpa_computation(
            InteractiveSessionState(threatened=True, evidence=True)
        )
        == "FDCPA violation is an affirmative defense."
    )
    assert (
        run_fdcpa_computation(
            InteractiveSessionState(disclosed=True, evidence=False)
        )
        == "FDCPA violation is a potential affirmative defense."
    )
    assert (
        run_fdcpa_computation(InteractiveSessionState())
        == "FDCPA violation is not an affirmative defense."
    )
