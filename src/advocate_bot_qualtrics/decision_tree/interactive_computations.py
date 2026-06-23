"""Compatibility shim — use advocate_bot_qualtrics.practice_areas.consumer_debt.computations."""

from advocate_bot_qualtrics.practice_areas.consumer_debt.computations import (
    SOL_LIMIT_DAYS,
    run_fdcpa_computation,
    run_sol_computation,
)

__all__ = ["SOL_LIMIT_DAYS", "run_fdcpa_computation", "run_sol_computation"]
