"""Compatibility shim — use advocate_bot_qualtrics.core.schemas."""

from advocate_bot_qualtrics.core.schemas import (  # noqa: F401
    ChatTurnResponse,
    CurrentNode,
    TreeBranch,
    UserIntent,
)

__all__ = ["ChatTurnResponse", "CurrentNode", "TreeBranch", "UserIntent"]
