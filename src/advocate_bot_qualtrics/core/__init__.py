"""Subject-agnostic junction engine and decision-tree primitives."""

from advocate_bot_qualtrics.core.bundle import PracticeAreaBundle, get_bundle, list_practice_areas
from advocate_bot_qualtrics.core.engine import (
    InteractiveChatEngine,
    InteractiveChatStep,
    MAX_TRANSCRIPT_TURNS,
    build_user_payload,
)
from advocate_bot_qualtrics.core.errors import ChatError
from advocate_bot_qualtrics.core.process_chat import process_chat
from advocate_bot_qualtrics.core.schemas import ChatTurnResponse, CurrentNode, TreeBranch, UserIntent
from advocate_bot_qualtrics.core.session import NodeAnswerRecord, record_node_answer

__all__ = [
    "ChatError",
    "ChatTurnResponse",
    "CurrentNode",
    "InteractiveChatEngine",
    "InteractiveChatStep",
    "MAX_TRANSCRIPT_TURNS",
    "NodeAnswerRecord",
    "PracticeAreaBundle",
    "TreeBranch",
    "UserIntent",
    "build_user_payload",
    "get_bundle",
    "list_practice_areas",
    "process_chat",
    "record_node_answer",
]
