"""Run simulated defendant conversations against InteractiveChatEngine."""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path

from advocate_bot_qualtrics.decision_tree.interactive_host import InteractiveChatEngine
from advocate_bot_qualtrics.fact_sheet_io import load_complaint_fact_sheet
from advocate_bot_qualtrics.simulator.schemas import (
    BatchConfig,
    SimulationConfig,
    SimulationResult,
    SimulationStatus,
    TurnRecord,
)
from advocate_bot_qualtrics.simulator.transcript import format_json_transcript, format_markdown_transcript
from advocate_bot_qualtrics.simulator.user_llm import generate_simulator_user_reply


def slugify_persona(text: str, *, fallback: str = "persona") -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    if not slug:
        return fallback
    return slug[:48]


def resolve_output_path(config: SimulationConfig) -> Path:
    if config.output_path is not None:
        return config.output_path
    output_dir = config.output_dir or Path("output/simulator_runs")
    timestamp = config.batch_timestamp or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    filename = f"{timestamp}_{config.persona_slug}_{config.run_index}.md"
    return output_dir / filename


def _last_assistant_message(transcript: list[tuple[str, str]]) -> str:
    for role, text in reversed(transcript):
        if role == "assistant":
            return text
    return ""


def _prompt_before_user_turn(transcript: list[tuple[str, str]]) -> str:
    if len(transcript) >= 2 and transcript[-1][0] == "user" and transcript[-2][0] == "assistant":
        return transcript[-2][1]
    return _last_assistant_message(transcript)


def _apply_session_fields_env(path: Path) -> None:
    os.environ["SESSION_FIELDS_XLSX_PATH"] = str(path.resolve())


def _write_transcripts(result: SimulationResult, config: SimulationConfig) -> None:
    path = resolve_output_path(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(format_markdown_transcript(result), encoding="utf-8")
    result.transcript_path = path.resolve()

    if config.write_json:
        json_path = path.with_suffix(".json")
        json_path.write_text(format_json_transcript(result), encoding="utf-8")
        result.json_path = json_path.resolve()


def run_single_simulation(
    config: SimulationConfig,
    *,
    user_reply_generator=generate_simulator_user_reply,
) -> SimulationResult:
    """Drive InteractiveChatEngine with a simulated defendant."""
    _apply_session_fields_env(config.session_fields_xlsx)

    engine = InteractiveChatEngine.from_fact_sheet(
        config.facts, practice_area_id=config.practice_area_id
    )
    opening = [text for role, text in engine.transcript if role == "assistant"]

    result = SimulationResult(
        config=config,
        status=SimulationStatus.COMPLETE,
        opening_assistant_messages=opening,
        started_at=datetime.now(timezone.utc),
    )

    turn_index = 0
    same_node_count = 0
    tree_user_turns = 0

    while not engine.tree_complete and tree_user_turns < config.max_turns:
        node_before = engine.current_node_id
        prompt_before = _prompt_before_user_turn(engine.transcript)

        try:
            reply = user_reply_generator(
                persona=config.persona,
                facts=config.facts,
                transcript=engine.transcript,
                last_assistant_message=prompt_before,
            )
        except Exception as exc:
            result.status = SimulationStatus.ERROR
            result.error_message = f"Simulator LLM error: {exc}"
            break

        step = engine.submit(reply.user_message)
        turn_index += 1
        tree_user_turns += 1

        record = TurnRecord(
            turn_index=turn_index,
            node_id_before=node_before,
            prompt_before=prompt_before,
            user_message=reply.user_message,
            simulator_notes=reply.notes,
            assistant_responses=list(step.assistant_messages),
            user_intent=step.user_intent,
            branch_id=step.branch_id,
            confidence_pct=step.confidence_pct,
            node_id_after=engine.current_node_id,
            tree_complete=engine.tree_complete,
            error=step.error,
            phase="tree",
        )
        result.turn_records.append(record)

        if step.error:
            result.status = SimulationStatus.ERROR
            result.error_message = step.error
            break

        if engine.current_node_id == node_before:
            same_node_count += 1
        else:
            same_node_count = 0

        if same_node_count >= config.stall_turns:
            result.status = SimulationStatus.STALLED
            result.stall_reason = (
                f"No tree progress for {config.stall_turns} consecutive turns "
                f"on node `{engine.current_node_id}`."
            )
            break

    if (
        result.status == SimulationStatus.COMPLETE
        and not engine.tree_complete
        and tree_user_turns >= config.max_turns
    ):
        result.status = SimulationStatus.MAX_TURNS

    qa_turns = 0
    while engine.tree_complete and qa_turns < config.qa_turns and result.status != SimulationStatus.ERROR:
        node_before = engine.current_node_id
        prompt_before = _prompt_before_user_turn(engine.transcript)

        try:
            reply = user_reply_generator(
                persona=config.persona,
                facts=config.facts,
                transcript=engine.transcript,
                last_assistant_message=prompt_before,
            )
        except Exception as exc:
            result.status = SimulationStatus.ERROR
            result.error_message = f"Simulator LLM error during Q&A: {exc}"
            break

        step = engine.submit(reply.user_message)
        turn_index += 1
        qa_turns += 1

        record = TurnRecord(
            turn_index=turn_index,
            node_id_before=node_before,
            prompt_before=prompt_before,
            user_message=reply.user_message,
            simulator_notes=reply.notes,
            assistant_responses=list(step.assistant_messages),
            user_intent=step.user_intent,
            branch_id=step.branch_id,
            confidence_pct=step.confidence_pct,
            node_id_after=engine.current_node_id,
            tree_complete=engine.tree_complete,
            error=step.error,
            phase="qa",
        )
        result.turn_records.append(record)

        if step.error:
            result.status = SimulationStatus.ERROR
            result.error_message = step.error
            break

    snapshot = engine.debug_snapshot(facts_path=str(config.facts_path))
    result.debug_snapshot = snapshot
    result.excel_path = snapshot.get("session_fields_xlsx") or None
    result.finished_at = datetime.now(timezone.utc)

    _write_transcripts(result, config)
    return result


def _load_batch_facts(batch: BatchConfig):
    if batch.practice_area_id == "consumer_debt":
        return load_complaint_fact_sheet(batch.facts_path)
    from advocate_bot_qualtrics.core.bundle import get_bundle

    return get_bundle(batch.practice_area_id).load_facts(batch.facts_path)


def run_batch(batch: BatchConfig, *, user_reply_generator=generate_simulator_user_reply) -> list[SimulationResult]:
    """Run one or more simulations across personas and repeats."""
    facts = _load_batch_facts(batch)
    timestamp = batch.batch_timestamp or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    batch.output_dir.mkdir(parents=True, exist_ok=True)

    results: list[SimulationResult] = []
    for slug, persona_text, _source in batch.personas:
        for run_index in range(1, batch.repeat + 1):
            config = SimulationConfig(
                facts=facts,
                facts_path=batch.facts_path.resolve(),
                persona=persona_text,
                persona_slug=slug,
                session_fields_xlsx=batch.session_fields_xlsx,
                output_dir=batch.output_dir,
                max_turns=batch.max_turns,
                stall_turns=batch.stall_turns,
                qa_turns=batch.qa_turns,
                write_json=batch.write_json,
                run_index=run_index,
                batch_timestamp=timestamp,
                practice_area_id=batch.practice_area_id,
            )
            results.append(
                run_single_simulation(config, user_reply_generator=user_reply_generator)
            )
    return results
