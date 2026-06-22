"""Configuration for the training-only interactive tree simulator."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

SIMULATOR_ROOT = Path(__file__).resolve().parent
PROMPTS_DIR = SIMULATOR_ROOT / "prompts"
SIMULATOR_USER_SYSTEM_PROMPT_PATH = PROMPTS_DIR / "simulator_user_system.md"

PROJECT_ROOT = SIMULATOR_ROOT.parents[2]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "output" / "simulator_runs"
DEFAULT_SESSION_FIELDS_XLSX = PROJECT_ROOT / "output" / "simulator_session_fields.xlsx"
DEFAULT_FACTS_JSON = PROJECT_ROOT / "fixtures" / "complaint_fact_sheet.sample.json"

DEFAULT_MAX_TURNS = 50
DEFAULT_STALL_TURNS = 5
DEFAULT_QA_TURNS = 0
DEFAULT_REPEAT = 1

SIMULATOR_TOOL_NAME = "submit_simulator_user_turn"


def get_simulator_user_model() -> str:
    """Model for role-playing the simulated defendant."""
    from advocate_bot_qualtrics.config import DEFAULT_ANTHROPIC_MODEL

    return os.getenv("SIMULATOR_USER_MODEL", DEFAULT_ANTHROPIC_MODEL).strip()


def load_simulator_user_system_prompt() -> str:
    if not SIMULATOR_USER_SYSTEM_PROMPT_PATH.is_file():
        raise FileNotFoundError(
            f"Simulator system prompt not found: {SIMULATOR_USER_SYSTEM_PROMPT_PATH}"
        )
    return SIMULATOR_USER_SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
