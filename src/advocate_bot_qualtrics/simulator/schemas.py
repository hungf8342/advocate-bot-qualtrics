"""Schemas for the interactive tree simulator."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from advocate_bot_qualtrics.schemas.complaint_fact_sheet import ComplaintFactSheet


class SimulationStatus(str, Enum):
    COMPLETE = "complete"
    STALLED = "stalled"
    ERROR = "error"
    MAX_TURNS = "max_turns"


class SimulatorUserTurn(BaseModel):
    """Structured simulator LLM output for one user reply."""

    user_message: str = Field(min_length=1)
    notes: str | None = Field(
        default=None,
        description="Optional brief reasoning for debug transcripts.",
    )


@dataclass
class TurnRecord:
    """One user turn plus host routing metadata."""

    turn_index: int
    node_id_before: str
    prompt_before: str
    user_message: str
    simulator_notes: str | None
    assistant_responses: list[str]
    user_intent: str | None
    branch_id: str | None
    confidence_pct: int | None
    node_id_after: str
    tree_complete: bool
    error: str | None = None
    phase: Literal["tree", "qa"] = "tree"


@dataclass
class SimulationConfig:
    facts: ComplaintFactSheet
    facts_path: Path
    persona: str
    persona_slug: str
    session_fields_xlsx: Path
    output_path: Path | None = None
    output_dir: Path | None = None
    max_turns: int = 50
    stall_turns: int = 5
    qa_turns: int = 0
    write_json: bool = False
    run_index: int = 1
    batch_timestamp: str | None = None
    practice_area_id: str = "consumer_debt"


@dataclass
class SimulationResult:
    config: SimulationConfig
    status: SimulationStatus
    turn_records: list[TurnRecord] = field(default_factory=list)
    opening_assistant_messages: list[str] = field(default_factory=list)
    debug_snapshot: dict[str, Any] = field(default_factory=dict)
    transcript_path: Path | None = None
    json_path: Path | None = None
    excel_path: str | None = None
    stall_reason: str | None = None
    error_message: str | None = None
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None


@dataclass
class BatchConfig:
    facts_path: Path
    personas: list[tuple[str, str, str]]  # slug, text, source label
    session_fields_xlsx: Path
    output_dir: Path
    max_turns: int = 50
    stall_turns: int = 5
    qa_turns: int = 0
    repeat: int = 1
    write_json: bool = False
    batch_timestamp: str | None = None
    practice_area_id: str = "consumer_debt"
