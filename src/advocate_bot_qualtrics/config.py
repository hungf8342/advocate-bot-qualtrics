"""Environment configuration."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parent.parent
PROMPTS_DIR = PROJECT_ROOT / "prompts"
CHAT_SYSTEM_PROMPT_PATH = PROMPTS_DIR / "decision_tree_chat_system.md"
CONFIDENCE_SCORING_CALIBRATION_PATH = PROMPTS_DIR / "confidence_scoring_calibration.md"
AUTONOMOUS_SYSTEM_PROMPT_PATH = PROMPTS_DIR / "decision_tree_autonomous_system.md"

DEFAULT_CONFIDENCE_HEDGE_THRESHOLD = 70
DEFAULT_SESSION_FIELDS_XLSX = PROJECT_ROOT / "output" / "session_fields.xlsx"


DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-6"
DEFAULT_ANTHROPIC_CHAT_MODEL = "claude-haiku-4-5-20251001"
DEFAULT_OPENAI_MODEL = "gpt-4o-2024-08-06"
DEFAULT_ZAI_BASE_URL = "https://api.z.ai/api/paas/v4/"
DEFAULT_ZAI_CHAT_MODEL = "glm-5.2"
DEFAULT_CHAT_PROVIDER = "zai"

CHAT_TOOL_NAME = "submit_chat_turn"


def get_llm_provider() -> str:
    return os.getenv("LLM_PROVIDER", "anthropic").strip().lower()


def get_anthropic_model() -> str:
    return os.getenv("ANTHROPIC_MODEL", DEFAULT_ANTHROPIC_MODEL)


def get_openai_model() -> str:
    return os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)


def get_anthropic_chat_model() -> str:
    """Chat model used by the decision-tree engine (Anthropic path; currently commented out)."""
    return os.getenv("ANTHROPIC_CHAT_MODEL", DEFAULT_ANTHROPIC_CHAT_MODEL)


def get_chat_provider() -> str:
    """Decision-tree chat router: ``zai`` (default) or ``anthropic``."""
    return os.getenv("CHAT_PROVIDER", DEFAULT_CHAT_PROVIDER).strip().lower()


def get_zai_api_key() -> str:
    return os.getenv("ZAI_API_KEY", "").strip()


def get_zai_chat_model() -> str:
    return os.getenv("ZAI_CHAT_MODEL", DEFAULT_ZAI_CHAT_MODEL)


def get_zai_base_url() -> str:
    return os.getenv("ZAI_BASE_URL", DEFAULT_ZAI_BASE_URL).strip()


def get_chat_api_key_hint() -> str:
    if get_chat_provider() == "anthropic":
        return "Check ANTHROPIC_API_KEY and retry."
    return "Check ZAI_API_KEY and retry."


def load_chat_system_prompt() -> str:
    if not CHAT_SYSTEM_PROMPT_PATH.is_file():
        raise FileNotFoundError(f"Decision-tree system prompt not found: {CHAT_SYSTEM_PROMPT_PATH}")
    return CHAT_SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")


def load_confidence_scoring_calibration() -> str:
    if not CONFIDENCE_SCORING_CALIBRATION_PATH.is_file():
        raise FileNotFoundError(
            f"Confidence calibration not found: {CONFIDENCE_SCORING_CALIBRATION_PATH}"
        )
    return CONFIDENCE_SCORING_CALIBRATION_PATH.read_text(encoding="utf-8")


def get_confidence_hedge_threshold() -> int:
    raw = os.getenv("CONFIDENCE_HEDGE_THRESHOLD", str(DEFAULT_CONFIDENCE_HEDGE_THRESHOLD))
    try:
        return int(raw)
    except ValueError:
        return DEFAULT_CONFIDENCE_HEDGE_THRESHOLD


def get_session_fields_xlsx_path() -> Path:
    raw = os.getenv("SESSION_FIELDS_XLSX_PATH", "").strip()
    if raw:
        return Path(raw)
    return DEFAULT_SESSION_FIELDS_XLSX


def load_autonomous_system_prompt() -> str:
    if not AUTONOMOUS_SYSTEM_PROMPT_PATH.is_file():
        raise FileNotFoundError(
            f"Autonomous decision-tree prompt not found: {AUTONOMOUS_SYSTEM_PROMPT_PATH}"
        )
    return AUTONOMOUS_SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
