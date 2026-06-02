from advocate_bot_qualtrics.decision_tree.schemas import ChatTurnResponse, CurrentNode, TreeBranch


def test_chat_turn_response_schema_contains_fields():
    schema = ChatTurnResponse.model_json_schema()
    props = schema["properties"]
    assert "user_intent" in props
    assert "assistant_reply" in props
    assert "next_node_id" in props


def test_current_node_schema_round_trip():
    node = CurrentNode(
        node_id="start",
        question="Q?",
        branches=[TreeBranch(branch_id="a", label="Yes"), TreeBranch(branch_id="b", label="No")],
    )
    assert [b.branch_id for b in node.branches] == ["a", "b"]
