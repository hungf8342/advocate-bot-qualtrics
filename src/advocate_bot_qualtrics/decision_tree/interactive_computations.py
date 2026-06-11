"""Host-side computation contracts for interactive tree hook nodes.

Hook nodes (`sol_computation`, `fdcpa_computation`) have no branches. The Qualtrics
host should run the logic below when landing on a hook node, then advance via
`advance_from_hook(node_id)`.
"""

from __future__ import annotations

from advocate_bot_qualtrics.decision_tree.interactive_session import InteractiveSessionState


def run_sol_computation(session: InteractiveSessionState) -> str:
    """Evaluate whether statute of limitations is an affirmative defense.

    Per Tree-Structures.docx:
    1. Take the most recent of:
       - last payment per complaint (`session.last_payment_complaint`)
       - last payment to original creditor (`session.last_payment_og_creditor`)
       - last payment to debt collector (`session.last_payment_debt_collector`)
    2. Compare `session.filing_date` minus that date.
    3. If more than 3 years, SOL is an affirmative defense; otherwise it is not.

    Returns a host-facing outcome label (implementation left to the host).
    """
    raise NotImplementedError(
        "SOL computation is host-owned; see docstring for the contract."
    )


def run_fdcpa_computation(session: InteractiveSessionState) -> str:
    """Classify FDCPA violation defense strength from session flags.

    Per Tree-Structures.docx:
    - If (`threatened` or `disclosed`) and `evidence`: affirmative defense.
    - If (`threatened` or `disclosed`) without `evidence`: potential affirmative defense.
    - If neither `threatened` nor `disclosed`: not an affirmative defense.

    Returns a host-facing outcome label (implementation left to the host).
    """
    raise NotImplementedError(
        "FDCPA computation is host-owned; see docstring for the contract."
    )
