"""Pydantic schemas for decision-tree chat."""

from __future__ import annotations

from pathlib import PurePosixPath
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ExplanationImage(BaseModel):
    """A project-local image referenced by an approved node explanation."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    path: str
    alt: str

    @field_validator("path")
    @classmethod
    def safe_relative_image(cls, path: str) -> str:
        parts = PurePosixPath(path)
        if (
            not path
            or re.fullmatch(r"[A-Za-z0-9_./-]+", path) is None
            or parts.is_absolute()
            or ".." in parts.parts
            or parts.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}
        ):
            raise ValueError("explanation images must use a relative image path")
        return path


class ExplanationBlock(BaseModel):
    """One paragraph in document order, optionally limited to a creditor type."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    text: str = Field(min_length=1)
    creditor_type: Literal["original", "buyer"] | None = None


class NodeExplanation(BaseModel):
    """Approved help text and optional visual examples for the active question."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    text: str = ""
    blocks: list[ExplanationBlock] = Field(default_factory=list)
    images: list[ExplanationImage] = Field(default_factory=list)
    show_with_question: bool = False

    @model_validator(mode="after")
    def validate_content(self) -> NodeExplanation:
        if bool(self.text) == bool(self.blocks):
            raise ValueError("explanation needs either text or ordered blocks")
        return self


class EnumValidation(BaseModel):
    """Meaning of each permitted category for answer classification."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    type: Literal["enum"]
    categories: dict[str, str]


class TreeBranch(BaseModel):
    """A valid choice that advances the decision tree."""

    model_config = ConfigDict(str_strip_whitespace=True)

    branch_id: str = Field(
        description="Allowed answer branch id; the host resolves it to a target node.",
    )
    label: str = Field(
        description="Human-readable option / matching hint.",
    )


DiscussionMode = Literal["screening", "decision", "clarification", "questions", "confirmation", "referral"]


class CurrentNode(BaseModel):
    """The current decision-tree node shown to the user."""

    model_config = ConfigDict(str_strip_whitespace=True)

    node_id: str = Field(description="Active node id passed as context to the LLM.")
    question: str = Field(description="Question the user should answer at this node.")
    title: str | None = None
    discussion_topic: str | None = None
    discussion_mode: DiscussionMode | None = None
    branches: list[TreeBranch] = Field(
        default_factory=list,
        description="Valid branches for advancing to the next node.",
    )
    explanation: NodeExplanation | None = None
    validation: EnumValidation | None = None


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
    answer_confidence_pct: int | None = Field(
        default=None,
        ge=0,
        le=100,
        description=(
            "Required when user_intent is 'answer_node': 0–100 confidence in the chosen branch, "
            "per confidence_scoring_calibration."
        ),
    )
