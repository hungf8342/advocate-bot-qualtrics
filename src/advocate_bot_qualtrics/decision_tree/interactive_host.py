"""Compatibility shim — use advocate_bot_qualtrics.core.engine."""

from advocate_bot_qualtrics.config import get_session_fields_xlsx_path
from advocate_bot_qualtrics.core.dates import parse_submitted_date
from advocate_bot_qualtrics.core.engine import (
    InteractiveChatEngine,
    InteractiveChatStep,
    MAX_TRANSCRIPT_TURNS,
    _process_terminal_qa,
    build_user_payload,
    render_interactive_node,
)
from advocate_bot_qualtrics.decision_tree.process_chat import process_chat

__all__ = [
    "InteractiveChatEngine",
    "InteractiveChatStep",
    "MAX_TRANSCRIPT_TURNS",
    "_process_terminal_qa",
    "build_user_payload",
    "get_session_fields_xlsx_path",
    "parse_submitted_date",
    "process_chat",
    "render_interactive_node",
]
