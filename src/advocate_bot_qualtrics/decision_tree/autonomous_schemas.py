"""Schemas for autonomous decision-tree traversal."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AutoBranch(BaseModel):
    """Branch metadata used by autonomous traversal."""

    model_config = ConfigDict(str_strip_whitespace=True)

    branch_id: str = Field(description="Unique branch id within a node.")
    target_node_id: str = Field(description="Target node id if this branch is selected.")
    label: str = Field(description="Human-friendly branch label.")
    selection_hint: str = Field(
        description="Branch selection hint describing when this branch should be chosen.",
    )


class AutoNode(BaseModel):
    """A node in the autonomous tree."""

    model_config = ConfigDict(str_strip_whitespace=True)

    node_id: str = Field(description="Stable unique node id.")
    instruction: str = Field(
        description="Instruction for this step. The model uses this plus fact-sheet data.",
    )
    branches: list[AutoBranch] = Field(default_factory=list, description="Valid branch options.")
    terminal_summary: str | None = Field(
        default=None,
        description="Optional terminal summary template for the final node.",
    )


class AutonomousStepSelection(BaseModel):
    """Structured model output for selecting the next autonomous branch."""

    model_config = ConfigDict(str_strip_whitespace=True)

    selected_branch_id: str | None = Field(
        default=None,
        description="Chosen branch id, or null when the current node is terminal.",
    )
    assistant_reply: str = Field(
        description="Assistant message describing this step and what it means for the user.",
    )


class AutoDecisionResult(BaseModel):
    """Final result returned after autonomous traversal."""

    model_config = ConfigDict(str_strip_whitespace=True)

    visited_nodes: list[str] = Field(default_factory=list)
    path_branch_ids: list[str] = Field(default_factory=list)
    final_node_id: str = Field(description="Final node reached by traversal.")
    summary: str = Field(description="Final assistant summary.")
    open_questions_prompt: str = Field(
        default="I have completed the decision-tree analysis from your complaint facts. Do you have any questions?",
        description="Final prompt inviting user questions.",
    )
