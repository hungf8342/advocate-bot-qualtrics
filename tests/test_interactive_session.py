import pytest

from advocate_bot_qualtrics.decision_tree.interactive_computations import (
    run_fdcpa_computation,
    run_sol_computation,
)
from advocate_bot_qualtrics.decision_tree.interactive_session import InteractiveSessionState


def test_run_sol_computation_not_implemented():
    with pytest.raises(NotImplementedError):
        run_sol_computation(InteractiveSessionState())


def test_run_fdcpa_computation_not_implemented():
    with pytest.raises(NotImplementedError):
        run_fdcpa_computation(InteractiveSessionState())
