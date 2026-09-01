"""Register the consumer debt practice area bundle."""

from __future__ import annotations

from typing import Any

from advocate_bot_qualtrics.config import (
    get_session_fields_xlsx_path,
    load_chat_system_prompt,
    load_confidence_scoring_calibration,
)
from advocate_bot_qualtrics.core.bundle import PracticeAreaBundle, register_bundle
from advocate_bot_qualtrics.practice_areas.consumer_debt.computations import (
    run_fdcpa_computation,
    run_sol_computation,
)
from advocate_bot_qualtrics.practice_areas.consumer_debt.date_confidence import (
    adjust_date_answer_confidence,
)
from advocate_bot_qualtrics.practice_areas.consumer_debt.field_export import append_session_fields_row
from advocate_bot_qualtrics.practice_areas.consumer_debt.host_extras import (
    DIFFERENT_COMPLAINT_RESTART_NODES,
    RESTART_FILING_CONFIRM_MESSAGE,
    build_debug_snapshot,
    consume_embedded_dispute_date,
    hook_outcome_key,
    render_node,
    skip_collected_date_node,
)
from advocate_bot_qualtrics.practice_areas.consumer_debt.session import (
    advance_from_hook,
    apply_interactive_branch,
    init_session,
    is_date_submit_node,
    is_interactive_hook_node,
)
from advocate_bot_qualtrics.practice_areas.consumer_debt.tree import (
    INTERACTIVE_START_NODE_ID,
    INTERACTIVE_TREE_DEFINITION,
    idk_skip_branch_for_node,
    resolve_interactive_next_node,
)

TERMINAL_NODE_ID = "review_questions"


def _run_hook(session: object, action: str) -> str:
    if action in {"sol_computation", "calculate_statute_of_limitations"}:
        return run_sol_computation(session)
    return run_fdcpa_computation(session)


def _facts_for_llm(_facts: object | None) -> dict[str, Any]:
    """No documents or extracted fact sheets are sent to the chat model."""
    return {}


def get_bundle() -> PracticeAreaBundle:
    return PracticeAreaBundle(
        id="consumer_debt",
        tree=INTERACTIVE_TREE_DEFINITION,
        start_node_id=INTERACTIVE_START_NODE_ID,
        terminal_node_id=TERMINAL_NODE_ID,
        facts_payload_key="user_provided_case_facts",
        load_chat_system_prompt=load_chat_system_prompt,
        load_calibration_prompt=load_confidence_scoring_calibration,
        get_session_fields_xlsx_path=get_session_fields_xlsx_path,
        init_session=init_session,
        is_hook_node=is_interactive_hook_node,
        advance_from_hook=advance_from_hook,
        is_date_submit_node=is_date_submit_node,
        apply_branch=apply_interactive_branch,
        adjust_date_answer_confidence=adjust_date_answer_confidence,
        resolve_next_node=resolve_interactive_next_node,
        idk_skip_branch=idk_skip_branch_for_node,
        run_hook=_run_hook,
        hook_outcome_key=hook_outcome_key,
        render_node=render_node,
        skip_collected_date_node=skip_collected_date_node,
        consume_embedded_dispute_date=consume_embedded_dispute_date,
        append_session_fields_row=append_session_fields_row,
        annotate_assistant_text=lambda text, _facts: text,
        build_debug_snapshot=build_debug_snapshot,
        facts_for_llm=_facts_for_llm,
        different_complaint_restart_nodes=DIFFERENT_COMPLAINT_RESTART_NODES,
        restart_filing_confirm_message=RESTART_FILING_CONFIRM_MESSAGE,
    )


def register() -> None:
    register_bundle(get_bundle())
