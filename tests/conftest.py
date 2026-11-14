"""Shared fixtures for deterministic intake and defense-rule tests."""

import pytest

from advocate_bot_qualtrics.practice_areas.consumer_debt.preliminary import PARSED_FIELDS
from advocate_bot_qualtrics.practice_areas.consumer_debt.session import (
    apply_interactive_branch,
    init_session,
)


@pytest.fixture
def verified_session():
    """Build recorded facts without importing a conversation engine or model."""
    def make(**overrides):
        values = {
            "PLAINTIFF.TYPE": "original", "PLAINTIFF": "Example Bank",
            "ORIGINAL.CREDITOR": "Example Original Bank", "SUIT.TYPE": "both",
            "OWNERSHIP": True, "OWNERSHIP.PROOF": True, "STATEMENT": True,
            "OPEN.DATE": "2020-01-01", "LAST.PAYMENT.DATE": "2025-01-01",
            "BREACH.DATE": "2025-02-01", "COMPLAINT.DATE": "2026-01-01",
        }
        values.update(overrides)
        session = init_session(values)
        for _, verification in PARSED_FIELDS.values():
            apply_interactive_branch(session, verification, "yes")
        for node, value in [("prelim_recognize", "yes"), ("prelim_oral", "no"),
                            ("prelim_consolidation", "no")]:
            apply_interactive_branch(session, node, value)
        return session

    return make
