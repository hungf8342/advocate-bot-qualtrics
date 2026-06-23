"""Compatibility shim — use advocate_bot_qualtrics.practice_areas.consumer_debt.tree."""

from advocate_bot_qualtrics.practice_areas.consumer_debt.tree import (
    INTERACTIVE_CONDITIONAL_ROUTE_NODES,
    INTERACTIVE_HOOK_ADVANCES,
    INTERACTIVE_HOOK_NODE_IDS,
    INTERACTIVE_IDK_SKIP_BRANCH,
    INTERACTIVE_ROUTES,
    INTERACTIVE_START_NODE_ID,
    INTERACTIVE_TREE,
    idk_skip_branch_for_node,
    resolve_interactive_next_node,
)

__all__ = [
    "INTERACTIVE_CONDITIONAL_ROUTE_NODES",
    "INTERACTIVE_HOOK_ADVANCES",
    "INTERACTIVE_HOOK_NODE_IDS",
    "INTERACTIVE_IDK_SKIP_BRANCH",
    "INTERACTIVE_ROUTES",
    "INTERACTIVE_START_NODE_ID",
    "INTERACTIVE_TREE",
    "idk_skip_branch_for_node",
    "resolve_interactive_next_node",
]
