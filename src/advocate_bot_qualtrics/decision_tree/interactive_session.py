"""Compatibility shim — use advocate_bot_qualtrics.practice_areas.consumer_debt.session."""

from advocate_bot_qualtrics.core.session import NodeAnswerRecord, record_node_answer
from advocate_bot_qualtrics.practice_areas.consumer_debt.session import (
    InteractiveSessionState,
    advance_from_hook,
    apply_interactive_branch,
    init_session_from_fact_sheet,
    is_interactive_hook_node,
)

__all__ = [
    "InteractiveSessionState",
    "NodeAnswerRecord",
    "advance_from_hook",
    "apply_interactive_branch",
    "init_session_from_fact_sheet",
    "is_interactive_hook_node",
    "record_node_answer",
]
