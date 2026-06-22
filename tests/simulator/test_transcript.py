"""Tests for simulator transcript formatting."""

from datetime import date, datetime, timezone

from advocate_bot_qualtrics.simulator.schemas import (
    SimulationConfig,
    SimulationResult,
    SimulationStatus,
    TurnRecord,
)
from advocate_bot_qualtrics.simulator.transcript import format_json_transcript, format_markdown_transcript
from advocate_bot_qualtrics.schemas.complaint_fact_sheet import ComplaintFactSheet


def _sample_config() -> SimulationConfig:
    return SimulationConfig(
        facts=ComplaintFactSheet(date_complaint_filed=date(2025, 9, 30)),
        facts_path=__import__("pathlib").Path("fixtures/sample.json"),
        persona="Ask lots of questions.",
        persona_slug="confused",
        session_fields_xlsx=__import__("pathlib").Path("output/sim.xlsx"),
        run_index=1,
    )


def test_markdown_includes_routing_fields():
    result = SimulationResult(
        config=_sample_config(),
        status=SimulationStatus.STALLED,
        opening_assistant_messages=["Was the claim filed on 2025-09-30?"],
        turn_records=[
            TurnRecord(
                turn_index=1,
                node_id_before="confirm_filing_date",
                prompt_before="Was the claim filed on 2025-09-30?",
                user_message="What's a filing date?",
                simulator_notes="Needs clarification.",
                assistant_responses=["The complaint was filed on 2025-09-30."],
                user_intent="ask_about_complaint",
                branch_id=None,
                confidence_pct=None,
                node_id_after="confirm_filing_date",
                tree_complete=False,
            )
        ],
        debug_snapshot={
            "tree_status": "In progress",
            "current_node_id": "confirm_filing_date",
            "node_answers": {},
        },
        stall_reason="stuck on node",
        started_at=datetime(2026, 6, 2, tzinfo=timezone.utc),
        finished_at=datetime(2026, 6, 2, tzinfo=timezone.utc),
    )

    text = format_markdown_transcript(result)

    assert "intent=`ask_about_complaint`" in text
    assert "branch=`—`" in text
    assert "confidence=`—`" in text
    assert "next_node=`confirm_filing_date`" in text
    assert "_Simulator notes:_ Needs clarification." in text
    assert "## Persona" in text
    assert "stuck on node" in text


def test_json_sidecar_structure():
    result = SimulationResult(
        config=_sample_config(),
        status=SimulationStatus.COMPLETE,
        turn_records=[],
        debug_snapshot={"tree_status": "Tree complete — ask anything"},
        started_at=datetime(2026, 6, 2, tzinfo=timezone.utc),
        finished_at=datetime(2026, 6, 2, tzinfo=timezone.utc),
    )

    payload = format_json_transcript(result)
    assert '"status": "complete"' in payload
    assert '"persona_slug": "confused"' in payload
    assert '"debug_snapshot"' in payload
