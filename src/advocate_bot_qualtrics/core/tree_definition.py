"""Declarative, validated definitions for interactive decision trees."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from advocate_bot_qualtrics.core.schemas import (
    CurrentNode, DiscussionMode, EnumValidation, NodeExplanation, TreeBranch,
)


NodeKind = Literal["choice", "condition", "input", "action", "terminal", "recommendation", "escalate", "notice"]
InputType = Literal["date", "text", "number", "currency"]


class InputDefinition(BaseModel):
    """How an input node stores and validates a user-provided value."""

    model_config = ConfigDict(extra="forbid")

    field: str
    type: InputType
    valid_branch_id: str = "submit"
    unknown_branch_id: str | None = None


class BranchDefinition(BaseModel):
    """One permitted answer and its explicit routing target."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: str
    label: str
    target: str
    embedded_input: InputDefinition | None = None


class CheckboxDefinition(BaseModel):
    """One checkbox whose explicit choice a decision records."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    defense_id: str = Field(min_length=1)
    checkbox_id: str = Field(min_length=1)
    label: str = Field(min_length=1)


class QuestionVariant(BaseModel):
    """Approved wording used when a practice-area fact has the specified value."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    fact_key: str = Field(min_length=1)
    equals: str = Field(min_length=1)
    text: str = Field(min_length=1)


class TreeNodeDefinition(BaseModel):
    """A declarative conversational node in an interactive tree."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: str
    kind: NodeKind
    question: str
    title: str | None = None
    discussion_topic: str | None = None
    discussion_mode: DiscussionMode | None = None
    branches: list[BranchDefinition] = Field(default_factory=list)
    input: InputDefinition | None = None
    action: str | None = None
    next: str | None = None
    idk_skip_branch_id: str | None = None
    terminal_qa: bool = False
    explanation: NodeExplanation | None = None
    validation: EnumValidation | None = None
    condition_key: str | None = Field(default=None, min_length=1)
    fact_key: str | None = Field(default=None, min_length=1)
    checkbox: CheckboxDefinition | None = None
    checkboxes: list[CheckboxDefinition] = Field(default_factory=list)
    question_variants: list[QuestionVariant] = Field(default_factory=list)
    fact_restatements: list[QuestionVariant] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_kind_configuration(self) -> TreeNodeDefinition:
        branch_ids = {branch.id for branch in self.branches}
        if self.condition_key is not None and self.kind != "condition":
            raise ValueError(f"node '{self.id}' only supports condition keys on conditions")
        if self.condition_key is not None and "unknown" not in branch_ids:
            raise ValueError(f"node '{self.id}' needs an unknown condition branch")
        if self.fact_key is not None and self.kind != "choice":
            raise ValueError(f"node '{self.id}' only captures categorical facts on choices")
        if (self.question_variants or self.fact_restatements) and self.kind == "condition":
            raise ValueError(f"condition node '{self.id}' cannot have question variants")
        if self.checkbox is not None and self.checkboxes:
            raise ValueError(f"node '{self.id}' cannot declare both checkbox and checkboxes")
        boxes = self.selection_checkboxes
        if boxes and (
            self.kind != "choice" or self.discussion_mode != "decision"
            or not {"yes", "no", "unknown"}.issubset(branch_ids) or self.fact_key
        ):
            raise ValueError(f"node '{self.id}' needs a distinct yes/no/unknown checkbox decision")
        if len({b.defense_id for b in boxes}) > 1 or len({b.checkbox_id for b in boxes}) != len(boxes):
            raise ValueError(f"node '{self.id}' checkbox group needs unique boxes from one defense")
        if (self.discussion_topic is None) != (self.discussion_mode is None):
            raise ValueError(f"node '{self.id}' needs both discussion topic and mode")
        if len(branch_ids) != len(self.branches):
            raise ValueError(f"node '{self.id}' has duplicate branch ids")
        if self.kind in {"choice", "condition"} and not self.branches:
            raise ValueError(f"{self.kind} node '{self.id}' needs branches")
        if self.kind == "condition" and (self.question or self.input or self.action):
            raise ValueError(f"condition node '{self.id}' cannot ask a question or run an action")
        if self.kind == "input":
            if self.input is None:
                raise ValueError(f"input node '{self.id}' needs input metadata")
            if self.input.valid_branch_id not in branch_ids:
                raise ValueError(f"input node '{self.id}' is missing its valid-input branch")
            if (
                self.input.unknown_branch_id is not None
                and self.input.unknown_branch_id not in branch_ids
            ):
                raise ValueError(f"input node '{self.id}' is missing its unknown branch")
        if self.kind == "action" and (not self.action or not self.next):
            raise ValueError(f"action node '{self.id}' needs action and next")
        if self.kind in {"terminal", "recommendation", "escalate"} and self.next:
            raise ValueError(f"terminal node '{self.id}' cannot define next")
        if self.idk_skip_branch_id is not None and self.idk_skip_branch_id not in branch_ids:
            raise ValueError(f"node '{self.id}' has an invalid idk skip branch")
        if self.validation is not None:
            if self.kind != "choice":
                raise ValueError(f"node '{self.id}' only supports enum validation on choice nodes")
            if set(self.validation.categories) != branch_ids or any(
                not description.strip() for description in self.validation.categories.values()
            ):
                raise ValueError(f"node '{self.id}' enum categories must describe every branch")
        return self

    @property
    def selection_checkboxes(self) -> list[CheckboxDefinition]:
        return [self.checkbox] if self.checkbox is not None else self.checkboxes

    def to_current_node(self) -> CurrentNode:
        return CurrentNode(
            node_id=self.id,
            question=self.question,
            title=self.title,
            discussion_topic=self.discussion_topic,
            discussion_mode=self.discussion_mode,
            branches=[
                TreeBranch(branch_id=branch.id, label=branch.label)
                for branch in self.branches
            ],
            explanation=self.explanation,
            validation=self.validation,
        )


class TreeDefinition(BaseModel):
    """The complete, versioned definition of a decision tree."""

    model_config = ConfigDict(extra="forbid")

    id: str
    version: str
    start_node_id: str
    nodes: list[TreeNodeDefinition]

    @model_validator(mode="after")
    def validate_references(self) -> TreeDefinition:
        node_ids = {node.id for node in self.nodes}
        if len(node_ids) != len(self.nodes):
            raise ValueError("tree has duplicate node ids")
        if self.start_node_id not in node_ids:
            raise ValueError("tree start_node_id does not exist")
        for node in self.nodes:
            for branch in node.branches:
                if branch.target not in node_ids:
                    raise ValueError(
                        f"node '{node.id}' branch '{branch.id}' targets unknown node '{branch.target}'"
                    )
            if node.next is not None and node.next not in node_ids:
                raise ValueError(f"node '{node.id}' next targets unknown node '{node.next}'")
        return self

    @property
    def node_map(self) -> dict[str, TreeNodeDefinition]:
        return {node.id: node for node in self.nodes}

    def node(self, node_id: str) -> TreeNodeDefinition:
        return self.node_map[node_id]

    def route(self, node_id: str, branch_id: str) -> str | None:
        for branch in self.node(node_id).branches:
            if branch.id == branch_id:
                return branch.target
        return None


def load_tree_definition(path: Path | str) -> TreeDefinition:
    """Load and fully validate a tree definition from YAML."""
    source = Path(path)
    with source.open(encoding="utf-8") as handle:
        # BaseLoader intentionally keeps unquoted identifiers such as ``yes`` and
        # ``no`` as strings. YAML 1.1 otherwise coerces them to booleans, which
        # is unsuitable for stable branch identifiers.
        data = yaml.load(handle, Loader=yaml.BaseLoader)
    return TreeDefinition.model_validate(data)
