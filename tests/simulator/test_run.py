"""Tests for simulator run loop."""

from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest

from advocate_bot_qualtrics.decision_tree.schemas import ChatTurnResponse
from advocate_bot_qualtrics.schemas.complaint_fact_sheet import ComplaintFactSheet
from advocate_bot_qualtrics.simulator.run import run_batch, run_single_simulation, slugify_persona
from advocate_bot_qualtrics.simulator.schemas import (
    BatchConfig,
    SimulationConfig,
    SimulationStatus,
    SimulatorUserTurn,
)


@pytest.fixture
def sample_facts() -> ComplaintFactSheet:
    return ComplaintFactSheet(
        date_complaint_filed=date(2025, 9, 30),
        date_user_failed_to_pay=date(2020, 12, 23),
    )


def _yes_turn() -> ChatTurnResponse:
    return ChatTurnResponse(
        user_intent="answer_node",
        assistant_reply="Got it.",
        next_node_id="yes",
        answer_confidence_pct=95,
    )


def _no_turn() -> ChatTurnResponse:
    return ChatTurnResponse(
        user_intent="answer_node",
        assistant_reply="Got it.",
        next_node_id="no",
        answer_confidence_pct=95,
    )


def _qa_turn() -> ChatTurnResponse:
    return ChatTurnResponse(
        user_intent="ask_about_complaint",
        assistant_reply="The complaint says the filing date is 2025-09-30.",
        next_node_id=None,
        answer_confidence_pct=None,
    )


def _sim_yes(**kwargs) -> SimulatorUserTurn:
    return SimulatorUserTurn(user_message="Yes.", notes=None)


def _sim_what(**kwargs) -> SimulatorUserTurn:
    return SimulatorUserTurn(user_message="What does that mean?", notes="Confused.")


@patch("advocate_bot_qualtrics.decision_tree.interactive_host.process_chat")
def test_run_completes_tree_with_mocks(mock_process_chat, sample_facts, tmp_path, monkeypatch):
    mock_process_chat.side_effect = [
        _yes_turn(),
        _yes_turn(),
        _no_turn(),
        _no_turn(),
        _no_turn(),
        _no_turn(),
    ]
    xlsx = tmp_path / "sim.xlsx"
    out = tmp_path / "run.md"
    monkeypatch.setattr(
        "advocate_bot_qualtrics.decision_tree.interactive_host.get_session_fields_xlsx_path",
        lambda: xlsx,
    )

    config = SimulationConfig(
        facts=sample_facts,
        facts_path=Path("fixtures/sample.json"),
        persona="Cooperative defendant.",
        persona_slug="cooperative",
        session_fields_xlsx=xlsx,
        output_path=out,
        max_turns=50,
        stall_turns=5,
    )
    result = run_single_simulation(config, user_reply_generator=_sim_yes)

    assert result.status == SimulationStatus.COMPLETE
    assert result.transcript_path == out.resolve()
    assert out.is_file()
    assert xlsx.is_file()
    assert "Routing:" in out.read_text(encoding="utf-8")
    assert result.debug_snapshot.get("tree_status", "").startswith("Tree complete")


@patch("advocate_bot_qualtrics.decision_tree.interactive_host.process_chat")
def test_stall_detection(mock_process_chat, sample_facts, tmp_path, monkeypatch):
    mock_process_chat.return_value = _qa_turn()
    xlsx = tmp_path / "sim.xlsx"
    out = tmp_path / "stalled.md"
    monkeypatch.setattr(
        "advocate_bot_qualtrics.decision_tree.interactive_host.get_session_fields_xlsx_path",
        lambda: xlsx,
    )

    config = SimulationConfig(
        facts=sample_facts,
        facts_path=Path("fixtures/sample.json"),
        persona="Always confused.",
        persona_slug="confused",
        session_fields_xlsx=xlsx,
        output_path=out,
        stall_turns=3,
        max_turns=20,
    )
    result = run_single_simulation(config, user_reply_generator=_sim_what)

    assert result.status == SimulationStatus.STALLED
    assert result.stall_reason is not None
    assert len(result.turn_records) == 3


@patch("advocate_bot_qualtrics.decision_tree.interactive_host.process_chat")
def test_error_stops_run(mock_process_chat, sample_facts, tmp_path, monkeypatch):
    from advocate_bot_qualtrics.decision_tree.errors import ChatError

    mock_process_chat.side_effect = ChatError("routing failed")
    xlsx = tmp_path / "sim.xlsx"
    out = tmp_path / "error.md"
    monkeypatch.setattr(
        "advocate_bot_qualtrics.decision_tree.interactive_host.get_session_fields_xlsx_path",
        lambda: xlsx,
    )

    config = SimulationConfig(
        facts=sample_facts,
        facts_path=Path("fixtures/sample.json"),
        persona="Cooperative.",
        persona_slug="cooperative",
        session_fields_xlsx=xlsx,
        output_path=out,
    )
    result = run_single_simulation(config, user_reply_generator=_sim_yes)

    assert result.status == SimulationStatus.ERROR
    assert result.error_message is not None
    assert result.turn_records[0].error is not None


def test_slugify_persona():
    assert slugify_persona("Pretend you're a defendant!!!") == "pretend_you_re_a_defendant"
    assert slugify_persona("!!!") == "persona"


@patch("advocate_bot_qualtrics.decision_tree.interactive_host.process_chat")
def test_batch_runs_multiple_outputs(mock_process_chat, sample_facts, tmp_path, monkeypatch):
    mock_process_chat.side_effect = [
        _yes_turn(),
        _yes_turn(),
        _no_turn(),
        _no_turn(),
        _no_turn(),
        _no_turn(),
    ] * 4
    xlsx = tmp_path / "sim.xlsx"
    persona_dir = tmp_path / "personas"
    persona_dir.mkdir()
    (persona_dir / "alpha.md").write_text("Alpha persona.", encoding="utf-8")
    (persona_dir / "beta.md").write_text("Beta persona.", encoding="utf-8")
    monkeypatch.setattr(
        "advocate_bot_qualtrics.decision_tree.interactive_host.get_session_fields_xlsx_path",
        lambda: xlsx,
    )

    batch = BatchConfig(
        facts_path=Path("fixtures/sample.json"),
        personas=[
            ("alpha", "Alpha persona.", str(persona_dir / "alpha.md")),
            ("beta", "Beta persona.", str(persona_dir / "beta.md")),
        ],
        session_fields_xlsx=xlsx,
        output_dir=tmp_path / "runs",
        repeat=2,
        batch_timestamp="20260602T120000Z",
    )

    with patch(
        "advocate_bot_qualtrics.simulator.run.load_complaint_fact_sheet",
        return_value=sample_facts,
    ):
        results = run_batch(batch, user_reply_generator=_sim_yes)

    assert len(results) == 4
    paths = {result.transcript_path for result in results}
    assert len(paths) == 4
    assert all(path.is_file() for path in paths if path is not None)
