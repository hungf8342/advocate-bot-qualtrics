"""Decision-tree chat entry point."""

from __future__ import annotations

from advocate_bot_qualtrics.config import load_chat_system_prompt
from advocate_bot_qualtrics.decision_tree.errors import ChatError
from advocate_bot_qualtrics.decision_tree.schemas import ChatTurnResponse, CurrentNode
from advocate_bot_qualtrics.llm.chat_structured import submit_chat_turn
from advocate_bot_qualtrics.schemas.complaint_fact_sheet import ComplaintFactSheet


def _post_validate_turn(
    turn: ChatTurnResponse, *, current_node: CurrentNode
) -> ChatTurnResponse:
    branch_ids = {b.branch_id for b in current_node.branches}

    if turn.user_intent != "answer_node":
        # next_node_id must be null unless we are advancing the tree.
        if turn.next_node_id is not None:
            return ChatTurnResponse.model_validate(
                {
                    **turn.model_dump(),
                    "next_node_id": None,
                }
            )
        return turn

    # user_intent == answer_node
    if not turn.next_node_id:
        raise ChatError(
            "LLM indicated the user answered the node, but next_node_id is null/empty."
        )

    if turn.next_node_id not in branch_ids:
        raise ChatError(
            "LLM chose a next_node_id not present in current_node.branches."
        )

    return turn


def process_chat(
    user_message: str,
    current_node: CurrentNode,
    fact_sheet: ComplaintFactSheet,
) -> ChatTurnResponse:
    """Process one decision-tree chat turn.

    Notes:
    - `user_message` may include a short host-prepared transcript of recent turns.
    - This function is responsible for enforcing strict `next_node_id` validity.
    """

    if not user_message or not user_message.strip():
        raise ValueError("user_message is empty.")

    system_prompt = load_chat_system_prompt()

    payload = {
        "current_node": current_node.model_dump(),
        # Keep prompt size down: audit quotes are optional; v1 decision tree should use facts.
        "complaint_fact_sheet": fact_sheet.model_dump(mode="json", exclude={"field_citations"}),
        "user_message": user_message,
    }

    turn = submit_chat_turn(system=system_prompt, payload=payload)

    return _post_validate_turn(turn, current_node=current_node)
