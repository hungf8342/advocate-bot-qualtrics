"""Compatibility shim — canonical process_chat for tests and legacy imports."""

from __future__ import annotations

from typing import Any

from advocate_bot_qualtrics.config import get_confidence_hedge_threshold
from advocate_bot_qualtrics.core.bundle import PracticeAreaBundle, get_bundle
from advocate_bot_qualtrics.core.confidence import clamp_answer_confidence, extract_latest_user_message
from advocate_bot_qualtrics.core.errors import ChatError
from advocate_bot_qualtrics.core.schemas import ChatTurnResponse, CurrentNode
from advocate_bot_qualtrics.llm.chat_structured import submit_chat_turn


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
    case_context: Any = None,
    bundle: PracticeAreaBundle | None = None,
    *,
    practice_area_id: str = "consumer_debt",
) -> ChatTurnResponse:
    """Process one decision-tree chat turn (default practice area: consumer_debt)."""

    if not user_message or not user_message.strip():
        raise ValueError("user_message is empty.")

    area = bundle or get_bundle(practice_area_id)
    latest_user_message = extract_latest_user_message(user_message)
    system_prompt = area.load_chat_system_prompt()

    payload = {
        "current_node": current_node.model_dump(),
        area.facts_payload_key: area.facts_for_llm(case_context),
        "user_message": user_message,
        "confidence_scoring_calibration": area.load_calibration_prompt(),
        "confidence_hedge_threshold": get_confidence_hedge_threshold(),
    }

    turn = submit_chat_turn(system=system_prompt, payload=payload)

    return _post_validate_turn(
        turn,
        current_node=current_node,
        latest_user_message=latest_user_message,
    )


__all__ = ["_post_validate_turn", "process_chat", "submit_chat_turn"]
