"""Confidence adjustments for approximate date answers."""

from __future__ import annotations

from advocate_bot_qualtrics.core.dates import ParsedDate
from advocate_bot_qualtrics.practice_areas.consumer_debt.computations import SOL_LIMIT_DAYS
from advocate_bot_qualtrics.practice_areas.consumer_debt.session import InteractiveSessionState

_APPROXIMATE_DATE_PENALTY = 15
_NEAR_THRESHOLD_PENALTY = 20
_NEAR_THRESHOLD_WINDOW_DAYS = 365


def adjust_date_answer_confidence(
    session: InteractiveSessionState,
    node_id: str,
    parsed: ParsedDate | None,
    base_confidence: int,
) -> int:
    if parsed is None or not parsed.approximate:
        return _clamp_confidence(base_confidence)

    adjusted = base_confidence - _APPROXIMATE_DATE_PENALTY
    if _is_near_sol_threshold(session, parsed):
        adjusted -= _NEAR_THRESHOLD_PENALTY
    return _clamp_confidence(adjusted)


def _is_near_sol_threshold(
    session: InteractiveSessionState,
    parsed: ParsedDate,
) -> bool:
    if session.filing_date is None:
        return False
    gap_days = (session.filing_date - parsed.value).days
    return abs(gap_days - SOL_LIMIT_DAYS) <= _NEAR_THRESHOLD_WINDOW_DAYS


def _clamp_confidence(value: int) -> int:
    return max(0, min(100, value))
