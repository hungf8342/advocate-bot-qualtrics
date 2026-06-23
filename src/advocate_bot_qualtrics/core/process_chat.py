"""Compatibility shim — use advocate_bot_qualtrics.core.process_chat."""

from advocate_bot_qualtrics.decision_tree.process_chat import (  # noqa: F401
    _post_validate_turn,
    process_chat,
    submit_chat_turn,
)

__all__ = ["_post_validate_turn", "process_chat", "submit_chat_turn"]
