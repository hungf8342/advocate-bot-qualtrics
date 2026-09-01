"""Practice-area bundle contract and registry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from advocate_bot_qualtrics.core.schemas import CurrentNode
from advocate_bot_qualtrics.core.tree_definition import TreeDefinition


@dataclass(frozen=True)
class PracticeAreaBundle:
    """Wires a subject-specific decision tree into the generic junction engine."""

    id: str
    tree: TreeDefinition
    start_node_id: str
    terminal_node_id: str
    facts_payload_key: str

    load_chat_system_prompt: Callable[[], str]
    load_calibration_prompt: Callable[[], str]
    get_session_fields_xlsx_path: Callable[[], Path]

    init_session: Callable[[Any], Any]
    is_hook_node: Callable[[str], bool]
    advance_from_hook: Callable[[str], str | None]
    is_date_submit_node: Callable[[str], bool]
    apply_branch: Callable[..., None]
    adjust_date_answer_confidence: Callable[..., int]
    resolve_next_node: Callable[..., str | None]
    idk_skip_branch: Callable[[str], str | None]
    run_hook: Callable[[Any, str], str]
    hook_outcome_key: Callable[[str], str | None]
    render_node: Callable[..., CurrentNode]
    skip_collected_date_node: Callable[[str, Any], str]
    consume_embedded_dispute_date: Callable[..., None]

    append_session_fields_row: Callable[..., Path]
    annotate_assistant_text: Callable[[str, Any], str]
    build_debug_snapshot: Callable[..., dict[str, Any]]
    facts_for_llm: Callable[[Any], dict[str, Any]]

    different_complaint_restart_nodes: frozenset[str]
    restart_filing_confirm_message: str


_REGISTRY: dict[str, PracticeAreaBundle] = {}


def register_bundle(bundle: PracticeAreaBundle) -> None:
    _REGISTRY[bundle.id] = bundle


def get_bundle(practice_area_id: str) -> PracticeAreaBundle:
    if practice_area_id not in _REGISTRY:
        raise KeyError(
            f"Unknown practice area '{practice_area_id}'. "
            f"Available: {', '.join(sorted(_REGISTRY)) or '(none)'}"
        )
    return _REGISTRY[practice_area_id]


def list_practice_areas() -> list[str]:
    return sorted(_REGISTRY)


def _register_defaults() -> None:
    from advocate_bot_qualtrics.practice_areas.consumer_debt.bundle import register

    register()


_register_defaults()
