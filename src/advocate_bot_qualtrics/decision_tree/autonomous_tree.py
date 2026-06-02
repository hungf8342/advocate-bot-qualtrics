"""Autonomous decision-tree node definitions (AI-driven mode)."""

from __future__ import annotations

from advocate_bot_qualtrics.decision_tree.autonomous_schemas import AutoBranch, AutoNode


AUTONOMOUS_START_NODE_ID = "check_amount_and_dates"


AUTONOMOUS_TREE: dict[str, AutoNode] = {
    "check_amount_and_dates": AutoNode(
        node_id="check_amount_and_dates",
        instruction=(
            "Determine whether the complaint facts include a principal amount sued for "
            "and at least one key timeline date (filed, alleged incident, or last payment)."
        ),
        branches=[
            AutoBranch(
                branch_id="sufficient",
                target_node_id="check_document_evidence",
                label="Amount and timeline are sufficiently populated",
                selection_hint=(
                    "Choose when amount_sued_for is present and at least one relevant date is present."
                ),
            ),
            AutoBranch(
                branch_id="missing_core_facts",
                target_node_id="terminal_missing_core_facts",
                label="Core amount/date facts are missing",
                selection_hint=(
                    "Choose when amount_sued_for is missing or all key dates are missing."
                ),
            ),
        ],
    ),
    "check_document_evidence": AutoNode(
        node_id="check_document_evidence",
        instruction=(
            "Determine whether documentary evidence flags suggest adequate debt ownership "
            "or payment-history support."
        ),
        branches=[
            AutoBranch(
                branch_id="evidence_present",
                target_node_id="terminal_ready_for_user_questions",
                label="At least one evidence indicator is present",
                selection_hint=(
                    "Choose when any of original_contract_included, "
                    "payment_or_balance_log_included, or "
                    "bill_of_assignment_or_debt_ownership_evidence is true."
                ),
            ),
            AutoBranch(
                branch_id="evidence_missing",
                target_node_id="terminal_missing_evidence",
                label="Evidence indicators are missing or unknown",
                selection_hint=(
                    "Choose when evidence flags are null/false across all documentary indicators."
                ),
            ),
        ],
    ),
    "terminal_missing_core_facts": AutoNode(
        node_id="terminal_missing_core_facts",
        instruction="Terminal node",
        branches=[],
        terminal_summary=(
            "Autonomous review found missing core facts (amount and/or timeline fields). "
            "Before relying on this path, verify extraction quality or source complaint text."
        ),
    ),
    "terminal_missing_evidence": AutoNode(
        node_id="terminal_missing_evidence",
        instruction="Terminal node",
        branches=[],
        terminal_summary=(
            "Autonomous review found weak documentary evidence signals in extracted facts. "
            "Consider validating exhibits and assignment records in the complaint package."
        ),
    ),
    "terminal_ready_for_user_questions": AutoNode(
        node_id="terminal_ready_for_user_questions",
        instruction="Terminal node",
        branches=[],
        terminal_summary=(
            "Autonomous review completed with core fields and some documentary support present. "
            "The analysis is ready for user questions."
        ),
    ),
}
