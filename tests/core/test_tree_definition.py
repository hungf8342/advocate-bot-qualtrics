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
    assert tree.version == "2026.10.25"
    assert tree.start_node_id == "verify_case_number"
    assert tree.node("get_filing_date").input.type == "date"
    assert tree.route("prelim_law_firm", "submit") == "verify_suit_type"
    assert tree.route("get_filing_date", "submit") == "verify_breach_date"
    assert tree.route("sol_creditor_type", "original") == "sol_payment_available"
    assert tree.route("sol_creditor_type", "buyer") == "sol_buyer"


def test_consumer_debt_tree_declares_inputs_actions_and_terminal_qa():
    assert INTERACTIVE_TREE_DEFINITION.node("get_filing_date").input is not None
    assert INTERACTIVE_TREE_DEFINITION.node("sol_finish").action.startswith("script_finish:")
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


@pytest.mark.parametrize('update,match',[
    ({'checkbox':{'defense_id':'test','checkbox_id':'main','label':'Test'}},'checkbox decision'),
    ({'condition_key':'field:PLAINTIFF'},'condition keys on conditions'),
    ({'fact_key':''},'at least 1 character'),
])
def test_script_metadata_cannot_bypass_node_kind_constraints(update,match):
    data=INTERACTIVE_TREE_DEFINITION.model_dump()
    node=data['nodes'][0]
    node.update(update)
    with pytest.raises(ValidationError,match=match):TreeDefinition.model_validate(data)


def test_bound_condition_requires_an_unknown_branch():
    data=INTERACTIVE_TREE_DEFINITION.model_dump()
    node=next(n for n in data['nodes'] if n['condition_key'])
    node['branches']=[b for b in node['branches'] if b['id']!='unknown']
    with pytest.raises(ValidationError,match='unknown condition branch'):TreeDefinition.model_validate(data)


@pytest.mark.parametrize('invalid_group', ['duplicate', 'mixed_defenses', 'both_forms'])
def test_checkbox_groups_reject_ambiguous_metadata(invalid_group):
    data = INTERACTIVE_TREE_DEFINITION.model_dump()
    node = next(n for n in data['nodes'] if n['checkboxes'])
    if invalid_group == 'duplicate':
        node['checkboxes'].append(node['checkboxes'][0].copy())
    elif invalid_group == 'mixed_defenses':
        node['checkboxes'][1]['defense_id'] = 'another_defense'
    else:
        node['checkbox'] = node['checkboxes'][0].copy()
    with pytest.raises(ValidationError, match='checkbox group|both checkbox and checkboxes'):
        TreeDefinition.model_validate(data)
