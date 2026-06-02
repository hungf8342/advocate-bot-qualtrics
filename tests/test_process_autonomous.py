import pytest

from advocate_bot_qualtrics.decision_tree.autonomous_schemas import AutonomousStepSelection
from advocate_bot_qualtrics.decision_tree.autonomous_tree import AUTONOMOUS_TREE
from advocate_bot_qualtrics.decision_tree.errors import ChatError
from advocate_bot_qualtrics.decision_tree.process_autonomous import process_autonomous
from advocate_bot_qualtrics.schemas.complaint_fact_sheet import ComplaintFactSheet


def _selector_choose_sufficient(node, _fact_sheet):
    if node.node_id == "check_amount_and_dates":
        return AutonomousStepSelection(
            selected_branch_id="sufficient",
            assistant_reply="Core fields look present.",
        )
    if node.node_id == "check_document_evidence":
        return AutonomousStepSelection(
            selected_branch_id="evidence_present",
            assistant_reply="Evidence appears present.",
        )
    return AutonomousStepSelection(selected_branch_id=None, assistant_reply="Terminal")


def test_process_autonomous_reaches_terminal():
    facts = ComplaintFactSheet(
        plaintiff_names=["Plaintiff"],
        defendant_names=["Defendant"],
        amount_sued_for="100.00",
    )
    start = AUTONOMOUS_TREE["check_amount_and_dates"]
    result = process_autonomous(
        facts,
        start,
        AUTONOMOUS_TREE,
        selector=_selector_choose_sufficient,
    )
    assert result.final_node_id == "terminal_ready_for_user_questions"
    assert result.visited_nodes[-1] == "terminal_ready_for_user_questions"
    assert result.path_branch_ids == ["sufficient", "evidence_present"]


def test_process_autonomous_invalid_branch_raises():
    facts = ComplaintFactSheet(
        plaintiff_names=["Plaintiff"],
        defendant_names=["Defendant"],
    )
    start = AUTONOMOUS_TREE["check_amount_and_dates"]

    def bad_selector(_node, _fact_sheet):
        return AutonomousStepSelection(
            selected_branch_id="not-a-valid-branch",
            assistant_reply="Bad route",
        )

    with pytest.raises(ChatError):
        process_autonomous(facts, start, AUTONOMOUS_TREE, selector=bad_selector)
