"""Decision-tree chat entry point."""

from __future__ import annotations

from advocate_bot_qualtrics.config import (
    get_confidence_hedge_threshold,
    load_chat_system_prompt,
    load_confidence_scoring_calibration,
)
from advocate_bot_qualtrics.decision_tree.confidence import (
    clamp_answer_confidence,
    extract_latest_user_message,
)
from advocate_bot_qualtrics.decision_tree.errors import ChatError
from advocate_bot_qualtrics.decision_tree.schemas import ChatTurnResponse, CurrentNode
from advocate_bot_qualtrics.llm.chat_structured import submit_chat_turn
from advocate_bot_qualtrics.schemas.complaint_fact_sheet import ComplaintFactSheet


def _post_validate_turn(
    turn: ChatTurnResponse,
    *,
    current_node: CurrentNode,
    latest_user_message: str,
) -> ChatTurnResponse:
    branch_ids = {b.branch_id for b in current_node.branches}

    if turn.user_intent != "answer_node":
        if turn.next_node_id is not None:
            return ChatTurnResponse.model_validate(
                {
                    **turn.model_dump(),
                    "next_node_id": None,
                    "answer_confidence_pct": None,
                }
            )
        return turn

    if not turn.next_node_id:
        raise ChatError(
            "LLM indicated the user answered the node, but next_node_id is null/empty."
        )

    if turn.next_node_id not in branch_ids:
        raise ChatError(
            "LLM chose a next_node_id not present in current_node.branches."
        )

    if turn.answer_confidence_pct is None:
        raise ChatError(
            "LLM indicated answer_node but answer_confidence_pct is null/empty."
        )

    clamped = clamp_answer_confidence(latest_user_message, turn.answer_confidence_pct)
    if clamped != turn.answer_confidence_pct:
        return ChatTurnResponse.model_validate(
            {**turn.model_dump(), "answer_confidence_pct": clamped}
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

    latest_user_message = extract_latest_user_message(user_message)
    system_prompt = load_chat_system_prompt()

    payload = {
        "current_node": current_node.model_dump(),
        "complaint_fact_sheet": fact_sheet.model_dump(mode="json", exclude={"field_citations"}),
        "user_message": user_message,
        "confidence_scoring_calibration": load_confidence_scoring_calibration(),
        "confidence_hedge_threshold": get_confidence_hedge_threshold(),
    }

    turn = submit_chat_turn(system=system_prompt, payload=payload)

    return _post_validate_turn(
        turn,
        current_node=current_node,
        latest_user_message=latest_user_message,
    )
