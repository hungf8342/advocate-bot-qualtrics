"""Rich transcript formatting for simulator runs."""

from __future__ import annotations

import json
from typing import Any

from advocate_bot_qualtrics.simulator.schemas import SimulationResult, SimulationStatus, TurnRecord


def _dash(value: Any) -> str:
    if value is None or value == "":
        return "—"
    return str(value)


def format_markdown_transcript(result: SimulationResult) -> str:
    cfg = result.config
    lines: list[str] = [
        "# Interactive tree simulator transcript",
        "",
        "## Run metadata",
        "",
        f"- **Started:** {result.started_at.isoformat()}",
        f"- **Finished:** {result.finished_at.isoformat() if result.finished_at else '—'}",
        f"- **Status:** {result.status.value}",
        f"- **Persona source:** {cfg.persona_slug}",
        f"- **Run index:** {cfg.run_index}",
        f"- **Facts file:** `{cfg.facts_path}`",
        f"- **Excel export:** `{result.excel_path or '—'}`",
        f"- **User turns:** {len(result.turn_records)}",
    ]

    if result.stall_reason:
        lines.append(f"- **Stall reason:** {result.stall_reason}")
    if result.error_message:
        lines.append(f"- **Error:** {result.error_message}")

    lines.extend(["", "## Persona", "", cfg.persona.strip() or "(default cooperative defendant)", ""])

    if result.opening_assistant_messages:
        lines.extend(["## Opening", ""])
        for message in result.opening_assistant_messages:
            lines.extend([f"**Assistant:** {message}", ""])

    for record in result.turn_records:
        lines.extend(_format_turn_block(record))

    lines.extend(["## Session summary", ""])
    lines.extend(_format_debug_snapshot(result.debug_snapshot))
    return "\n".join(lines).rstrip() + "\n"


def _format_turn_block(record: TurnRecord) -> list[str]:
    phase_label = "Q&A" if record.phase == "qa" else record.node_id_before
    lines = [
        f"### Turn {record.turn_index} — {phase_label}",
        "",
        f"**Assistant:** {record.prompt_before}",
        "",
        f"**User (simulator):** {record.user_message}",
        "",
    ]

    if record.simulator_notes:
        lines.extend([f"_Simulator notes:_ {record.simulator_notes}", ""])

    lines.extend([
        "**Routing:** "
        f"intent=`{_dash(record.user_intent)}` | "
        f"branch=`{_dash(record.branch_id)}` | "
        f"confidence=`{_dash(record.confidence_pct)}` | "
        f"next_node=`{_dash(record.node_id_after)}`",
        "",
    ])

    if record.error:
        lines.extend([f"**Error:** {record.error}", ""])
        return lines

    for message in record.assistant_responses:
        lines.extend([f"**Assistant:** {message}", ""])

    return lines


def _format_debug_snapshot(snapshot: dict[str, Any]) -> list[str]:
    if not snapshot:
        return ["- (no snapshot)"]

    lines = [
        f"- **Tree status:** {snapshot.get('tree_status', '—')}",
        f"- **Current node:** `{snapshot.get('current_node_id', '—')}`",
        f"- **Filing date:** {snapshot.get('filing_date', '—')}",
        f"- **Last payment (complaint):** {snapshot.get('last_payment_complaint', '—')}",
        f"- **Last payment (OG creditor):** {snapshot.get('last_payment_og_creditor', '—')}",
        f"- **Last payment (debt collector):** {snapshot.get('last_payment_debt_collector', '—')}",
        f"- **Filing date changed:** {snapshot.get('filing_date_changed', '—')}",
        f"- **Last payment changed:** {snapshot.get('last_payment_date_changed', '—')}",
        f"- **SOL outcome:** {snapshot.get('sol_outcome', '—')}",
        f"- **FDCPA outcome:** {snapshot.get('fdcpa_outcome', '—')}",
        "",
        "**Node answers (confidence)**",
        "",
    ]

    node_answers = snapshot.get("node_answers") or {}
    if not node_answers:
        lines.append("- (none)")
    else:
        for node_id, record in node_answers.items():
            skipped = " skipped" if record.get("skipped") else ""
            lines.append(
                f"- `{node_id}`: {record.get('branch')} @ {record.get('confidence_pct')}%{skipped}"
            )

    return lines


def format_json_transcript(result: SimulationResult) -> str:
    payload = {
        "metadata": {
            "status": result.status.value,
            "started_at": result.started_at.isoformat(),
            "finished_at": result.finished_at.isoformat() if result.finished_at else None,
            "persona_slug": result.config.persona_slug,
            "persona": result.config.persona,
            "facts_path": str(result.config.facts_path),
            "run_index": result.config.run_index,
            "excel_path": result.excel_path,
            "stall_reason": result.stall_reason,
            "error_message": result.error_message,
        },
        "opening_assistant_messages": result.opening_assistant_messages,
        "turn_records": [
            {
                "turn_index": record.turn_index,
                "phase": record.phase,
                "node_id_before": record.node_id_before,
                "user_message": record.user_message,
                "simulator_notes": record.simulator_notes,
                "prompt_before": record.prompt_before,
                "assistant_responses": record.assistant_responses,
                "user_intent": record.user_intent,
                "branch_id": record.branch_id,
                "confidence_pct": record.confidence_pct,
                "node_id_after": record.node_id_after,
                "tree_complete": record.tree_complete,
                "error": record.error,
            }
            for record in result.turn_records
        ],
        "debug_snapshot": result.debug_snapshot,
    }
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def status_from_result(result: SimulationResult) -> SimulationStatus:
    return result.status
