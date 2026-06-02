"""Pydantic schemas for decision-tree chat."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TreeBranch(BaseModel):
    """A valid choice that advances the decision tree."""

    model_config = ConfigDict(str_strip_whitespace=True)

    branch_id: str = Field(
        description="Target node id when this branch is chosen.",
    )
    label: str = Field(
        description="Human-readable option / matching hint.",
    )


class CurrentNode(BaseModel):
    """The current decision-tree node shown to the user."""

    model_config = ConfigDict(str_strip_whitespace=True)

    node_id: str = Field(description="Active node id passed as context to the LLM.")
    question: str = Field(description="Question the user should answer at this node.")
    branches: list[TreeBranch] = Field(
        default_factory=list,
        description="Valid branches for advancing to the next node.",
    )


UserIntent = Literal[
    "answer_node",
    "ask_about_complaint",
    "off_topic",
    "unclear",
]


class ChatTurnResponse(BaseModel):
    """Structured response from the LLM for a single chat turn."""

    model_config = ConfigDict(str_strip_whitespace=True)

    user_intent: UserIntent = Field(description="Intent classification for the host app.")
    assistant_reply: str = Field(description="User-facing response message.")
    next_node_id: str | None = Field(
        default=None,
        description=(
            "If and only if user_intent is 'answer_node', set next_node_id to one of the provided branch_id values."
        ),
    )
