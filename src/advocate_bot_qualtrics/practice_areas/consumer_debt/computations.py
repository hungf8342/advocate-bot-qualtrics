"""Host-side computation for interactive tree hook nodes.

Hook nodes (`sol_computation`, `fdcpa_computation`) have no branches. The host
runs the logic below when landing on a hook node, then advances via
`advance_from_hook(node_id)`.
"""

from __future__ import annotations

from datetime import date

from advocate_bot_qualtrics.practice_areas.consumer_debt.session import InteractiveSessionState

# Demo approximation of a three-year limit (~3 * 365 days), not calendar-year legal analysis.
SOL_LIMIT_DAYS = 1095


def run_sol_computation(session: InteractiveSessionState) -> str:
    """Evaluate whether statute of limitations is an affirmative defense.

    Per Tree-Structures.docx:
    1. Take the most recent of complaint, OG-creditor, and debt-collector payment dates.
    2. Compare filing date minus that date.
    3. If more than SOL_LIMIT_DAYS, SOL is an affirmative defense; otherwise it is not.
    """
    if session.filing_date is None:
        return "Insufficient date information to evaluate SOL."

    payment_dates: list[date] = [
        d
        for d in (
            session.last_payment_complaint,
            session.last_payment_og_creditor,
            session.last_payment_debt_collector,
        )
        if d is not None
    ]
    if not payment_dates:
        return "Insufficient date information to evaluate SOL."

    last_payment = max(payment_dates)
    if (session.filing_date - last_payment).days > SOL_LIMIT_DAYS:
        return "SOL is an affirmative defense."
    return "SOL is not an affirmative defense."


def run_fdcpa_computation(session: InteractiveSessionState) -> str:
    """Classify FDCPA violation defense strength from session flags."""
    conduct = session.threatened or session.disclosed
    if conduct and session.evidence:
        return "FDCPA violation is an affirmative defense."
    if conduct:
        return "FDCPA violation is a potential affirmative defense."
    return "FDCPA violation is not an affirmative defense."
