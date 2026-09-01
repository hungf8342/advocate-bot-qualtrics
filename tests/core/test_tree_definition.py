"""Validation coverage for declarative interactive tree definitions."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from advocate_bot_qualtrics.core.tree_definition import TreeDefinition, load_tree_definition
from advocate_bot_qualtrics.practice_areas.consumer_debt.tree import (
    INTERACTIVE_TREE_DEFINITION,
    INTERACTIVE_TREE_PATH,
)


def test_consumer_debt_tree_loads_from_yaml_with_string_branch_ids():
    tree = load_tree_definition(INTERACTIVE_TREE_PATH)

    assert tree.id == "consumer_debt_interactive"
    assert tree.version == "1.2"
    assert tree.start_node_id == "get_plaintiff_name"
    assert tree.node("get_plaintiff_name").input.type == "text"
    assert tree.route("get_plaintiff_name", "submit") == "get_amount_sued"


def test_consumer_debt_tree_declares_inputs_actions_and_terminal_qa():
    assert INTERACTIVE_TREE_DEFINITION.node("get_filing_date").input is not None
    assert INTERACTIVE_TREE_DEFINITION.node("sol_computation").action == "sol_computation"
    assert INTERACTIVE_TREE_DEFINITION.node("review_questions").terminal_qa is True


def test_tree_validator_rejects_unknown_branch_targets():
    with pytest.raises(ValidationError, match="targets unknown node"):
        TreeDefinition.model_validate(
            {
                "id": "invalid",
                "version": "1",
                "start_node_id": "start",
                "nodes": [
                    {
                        "id": "start",
                        "kind": "choice",
                        "question": "Choose.",
                        "branches": [{"id": "continue", "label": "Continue", "target": "missing"}],
                    }
                ],
            }
        )
