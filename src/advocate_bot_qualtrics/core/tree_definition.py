"""Declarative, validated definitions for interactive decision trees."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from advocate_bot_qualtrics.core.schemas import CurrentNode, TreeBranch


NodeKind = Literal["choice", "input", "action", "terminal", "recommendation", "escalate", "notice"]
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


class TreeNodeDefinition(BaseModel):
    """A declarative conversational node in an interactive tree."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: str
    kind: NodeKind
    question: str
    branches: list[BranchDefinition] = Field(default_factory=list)
    input: InputDefinition | None = None
    action: str | None = None
    next: str | None = None
    idk_skip_branch_id: str | None = None
    terminal_qa: bool = False

    @model_validator(mode="after")
    def validate_kind_configuration(self) -> TreeNodeDefinition:
        branch_ids = {branch.id for branch in self.branches}
        if len(branch_ids) != len(self.branches):
            raise ValueError(f"node '{self.id}' has duplicate branch ids")
        if self.kind == "choice" and not self.branches:
            raise ValueError(f"choice node '{self.id}' needs branches")
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
        return self

    def to_current_node(self) -> CurrentNode:
        return CurrentNode(
            node_id=self.id,
            question=self.question,
            branches=[
                TreeBranch(branch_id=branch.id, label=branch.label)
                for branch in self.branches
            ],
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
