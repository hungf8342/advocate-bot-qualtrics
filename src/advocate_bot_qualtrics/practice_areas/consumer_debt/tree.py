"""Declarative interactive consumer-debt tree and compatibility exports.

The canonical tree lives in ``interactive_tree.yaml``.  This module preserves
the former Python constants for callers and tests during the migration.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from advocate_bot_qualtrics.core.schemas import CurrentNode
from advocate_bot_qualtrics.core.tree_definition import TreeDefinition, load_tree_definition

if TYPE_CHECKING:
    from advocate_bot_qualtrics.practice_areas.consumer_debt.session import InteractiveSessionState


INTERACTIVE_TREE_PATH = Path(__file__).with_name("interactive_tree.yaml")
INTERACTIVE_TREE_DEFINITION: TreeDefinition = load_tree_definition(INTERACTIVE_TREE_PATH)
INTERACTIVE_START_NODE_ID = INTERACTIVE_TREE_DEFINITION.start_node_id
INTERACTIVE_TREE: dict[str, CurrentNode] = {
    node.id: node.to_current_node() for node in INTERACTIVE_TREE_DEFINITION.nodes
}

INTERACTIVE_HOOK_NODE_IDS: frozenset[str] = frozenset(
    node.id for node in INTERACTIVE_TREE_DEFINITION.nodes if node.kind == "action"
)
INTERACTIVE_HOOK_ADVANCES: dict[str, str] = {
    node.id: node.next
    for node in INTERACTIVE_TREE_DEFINITION.nodes
    if node.kind == "action" and node.next is not None
}
INTERACTIVE_IDK_SKIP_BRANCH: dict[str, str] = {
    node.id: node.idk_skip_branch_id
    for node in INTERACTIVE_TREE_DEFINITION.nodes
    if node.idk_skip_branch_id is not None
}
INTERACTIVE_ROUTES: dict[tuple[str, str], str] = {
    (node.id, branch.id): branch.target
    for node in INTERACTIVE_TREE_DEFINITION.nodes
    for branch in node.branches
}
INTERACTIVE_CONDITIONAL_ROUTE_NODES: frozenset[str] = frozenset({"contact_third_parties"})


def idk_skip_branch_for_node(node_id: str) -> str | None:
    return INTERACTIVE_TREE_DEFINITION.node(node_id).idk_skip_branch_id


def resolve_interactive_next_node(
    current_node_id: str,
    branch_id: str,
    session: InteractiveSessionState | None = None,
) -> str | None:
    """Resolve an explicit branch target, with one legacy state guard."""
    if current_node_id == "contact_third_parties":
        if session is not None and not session.threatened and not session.disclosed:
            return "fdcpa_computation"
    return INTERACTIVE_TREE_DEFINITION.route(current_node_id, branch_id)
