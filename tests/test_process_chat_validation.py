import pytest

from advocate_bot_qualtrics.decision_tree.errors import ChatError
from advocate_bot_qualtrics.decision_tree.process_chat import _post_validate_turn
from advocate_bot_qualtrics.decision_tree.schemas import ChatTurnResponse, CurrentNode, TreeBranch


def test_post_validate_sets_next_node_null_for_non_answer_intent():
    node = CurrentNode(
        node_id="n1",
        question="Q",
        branches=[TreeBranch(branch_id="yes", label="Yes")],
    )
    turn = ChatTurnResponse(
        user_intent="ask_about_complaint",
        assistant_reply="some",
        next_node_id="yes",
    )
    out = _post_validate_turn(turn, current_node=node)
    assert out.user_intent == "ask_about_complaint"
    assert out.next_node_id is None


def test_post_validate_rejects_invalid_branch_id():
    node = CurrentNode(
        node_id="n1",
        question="Q",
        branches=[TreeBranch(branch_id="yes", label="Yes"), TreeBranch(branch_id="no", label="No")],
    )

    turn = ChatTurnResponse(
        user_intent="answer_node",
        assistant_reply="reply",
        next_node_id="maybe",
    )

    with pytest.raises(ChatError):
        _post_validate_turn(turn, current_node=node)


def test_post_validate_rejects_missing_next_node_id_for_answer_node():
    node = CurrentNode(
        node_id="n1",
        question="Q",
        branches=[TreeBranch(branch_id="yes", label="Yes")],
    )

    turn = ChatTurnResponse(
        user_intent="answer_node",
        assistant_reply="reply",
        next_node_id=None,
    )

    with pytest.raises(ChatError):
        _post_validate_turn(turn, current_node=node)
