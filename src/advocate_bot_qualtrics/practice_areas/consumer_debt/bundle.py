"""Register the consumer debt practice area bundle."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from advocate_bot_qualtrics.config import (
    get_session_fields_xlsx_path,
    load_chat_system_prompt,
    load_confidence_scoring_calibration,
)
from advocate_bot_qualtrics.core.bundle import PracticeAreaBundle, register_bundle
from advocate_bot_qualtrics.fact_sheet_io import load_complaint_fact_sheet
from advocate_bot_qualtrics.practice_areas.consumer_debt.computations import (
    run_fdcpa_computation,
    run_sol_computation,
)
from advocate_bot_qualtrics.practice_areas.consumer_debt.fact_sheet import ComplaintFactSheet
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
from advocate_bot_qualtrics.practice_areas.consumer_debt.party_labels import annotate_party_terms
from advocate_bot_qualtrics.practice_areas.consumer_debt.session import (
    advance_from_hook,
    apply_interactive_branch,
    init_session_from_fact_sheet,
    is_interactive_hook_node,
)
from advocate_bot_qualtrics.practice_areas.consumer_debt.tree import (
    INTERACTIVE_START_NODE_ID,
    idk_skip_branch_for_node,
    resolve_interactive_next_node,
)

TERMINAL_NODE_ID = "review_questions"


def _run_hook(session: object, node_id: str) -> str:
    if node_id == "sol_computation":
        return run_sol_computation(session)
    return run_fdcpa_computation(session)


def _facts_for_llm(facts: ComplaintFactSheet) -> dict[str, Any]:
    return facts.model_dump(mode="json", exclude={"field_citations"})


def _load_facts(path: Path | str) -> ComplaintFactSheet:
    return load_complaint_fact_sheet(path)


def get_bundle() -> PracticeAreaBundle:
    return PracticeAreaBundle(
        id="consumer_debt",
        start_node_id=INTERACTIVE_START_NODE_ID,
        terminal_node_id=TERMINAL_NODE_ID,
        facts_payload_key="complaint_fact_sheet",
        load_facts=_load_facts,
        load_chat_system_prompt=load_chat_system_prompt,
        load_calibration_prompt=load_confidence_scoring_calibration,
        get_session_fields_xlsx_path=get_session_fields_xlsx_path,
        init_session=init_session_from_fact_sheet,
        is_hook_node=is_interactive_hook_node,
        advance_from_hook=advance_from_hook,
        apply_branch=apply_interactive_branch,
        resolve_next_node=resolve_interactive_next_node,
        idk_skip_branch=idk_skip_branch_for_node,
        run_hook=_run_hook,
        hook_outcome_key=hook_outcome_key,
        render_node=render_node,
        skip_collected_date_node=skip_collected_date_node,
        consume_embedded_dispute_date=consume_embedded_dispute_date,
        append_session_fields_row=append_session_fields_row,
        annotate_assistant_text=annotate_party_terms,
        build_debug_snapshot=build_debug_snapshot,
        facts_for_llm=_facts_for_llm,
        different_complaint_restart_nodes=DIFFERENT_COMPLAINT_RESTART_NODES,
        restart_filing_confirm_message=RESTART_FILING_CONFIRM_MESSAGE,
    )


def register() -> None:
    register_bundle(get_bundle())
