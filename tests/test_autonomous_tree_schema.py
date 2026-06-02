from advocate_bot_qualtrics.decision_tree.autonomous_schemas import (
    AutoDecisionResult,
    AutoNode,
)
from advocate_bot_qualtrics.decision_tree.autonomous_tree import AUTONOMOUS_TREE


def test_autonomous_tree_nodes_validate():
    assert "check_amount_and_dates" in AUTONOMOUS_TREE
    for node in AUTONOMOUS_TREE.values():
        assert isinstance(node, AutoNode)


def test_auto_decision_result_defaults():
    result = AutoDecisionResult(final_node_id="terminal", summary="Done")
    assert result.visited_nodes == []
    assert result.path_branch_ids == []
    assert "Do you have any questions?" in result.open_questions_prompt
