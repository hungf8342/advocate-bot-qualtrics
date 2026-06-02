"""Autonomous decision-tree traversal runner."""

from __future__ import annotations

from typing import Callable

from advocate_bot_qualtrics.decision_tree.autonomous_schemas import (
    AutoDecisionResult,
    AutoNode,
    AutonomousStepSelection,
)
from advocate_bot_qualtrics.decision_tree.errors import ChatError
from advocate_bot_qualtrics.llm.autonomous_structured import select_autonomous_branch
from advocate_bot_qualtrics.schemas.complaint_fact_sheet import ComplaintFactSheet


def _validate_branch_selection(
    node: AutoNode,
    selection: AutonomousStepSelection,
) -> str | None:
    valid_ids = {branch.branch_id for branch in node.branches}

    if not node.branches:
        # Terminal nodes should not select further branches.
        return None

    selected = selection.selected_branch_id
    if not selected:
        raise ChatError(
            f"Autonomous selector returned null branch for non-terminal node '{node.node_id}'."
        )
    if selected not in valid_ids:
        raise ChatError(
            f"Autonomous selector returned invalid branch '{selected}' for node '{node.node_id}'."
        )
    return selected


def process_autonomous(
    fact_sheet: ComplaintFactSheet,
    start_node: AutoNode,
    tree_map: dict[str, AutoNode],
    *,
    max_steps: int = 25,
    selector: Callable[[AutoNode, ComplaintFactSheet], AutonomousStepSelection]
    | None = None,
) -> AutoDecisionResult:
    """Traverse the autonomous tree from `start_node` using fact-sheet data only."""
    if max_steps < 1:
        raise ValueError("max_steps must be >= 1")

    select = selector or (lambda node, fs: select_autonomous_branch(node=node, fact_sheet=fs))

    current = start_node
    visited_nodes: list[str] = []
    path_branch_ids: list[str] = []
    latest_reply = ""

    for _ in range(max_steps):
        visited_nodes.append(current.node_id)

        if not current.branches:
            summary = current.terminal_summary or latest_reply or (
                "Autonomous traversal completed with no additional recommendations."
            )
            return AutoDecisionResult(
                visited_nodes=visited_nodes,
                path_branch_ids=path_branch_ids,
                final_node_id=current.node_id,
                summary=summary,
            )

        selection = select(current, fact_sheet)
        latest_reply = selection.assistant_reply
        branch_id = _validate_branch_selection(current, selection)
        if branch_id is None:
            return AutoDecisionResult(
                visited_nodes=visited_nodes,
                path_branch_ids=path_branch_ids,
                final_node_id=current.node_id,
                summary=latest_reply
                or "Autonomous traversal completed. Do you have any questions?",
            )

        branch = next(branch for branch in current.branches if branch.branch_id == branch_id)
        path_branch_ids.append(branch_id)

        if branch.target_node_id not in tree_map:
            raise ChatError(
                f"Tree map is missing target node '{branch.target_node_id}' "
                f"from branch '{branch_id}' on '{current.node_id}'."
            )
        current = tree_map[branch.target_node_id]

    raise ChatError(
        "Autonomous traversal hit max_steps without reaching a terminal node. "
        "Check for loops in autonomous_tree definitions."
    )
