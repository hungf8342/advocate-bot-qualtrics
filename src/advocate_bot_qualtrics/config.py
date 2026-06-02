"""Environment configuration."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parent.parent
PROMPTS_DIR = PROJECT_ROOT / "prompts"
SYSTEM_PROMPT_PATH = PROMPTS_DIR / "complaint_extraction_system.md"
CHAT_SYSTEM_PROMPT_PATH = PROMPTS_DIR / "decision_tree_chat_system.md"

MAX_COMPLAINT_CHARS = 100_000

DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-6"
DEFAULT_ANTHROPIC_CHAT_MODEL = "claude-haiku-4-5-20251001"
DEFAULT_OPENAI_MODEL = "gpt-4o-2024-08-06"

TOOL_NAME = "submit_complaint_fact_sheet"
CHAT_TOOL_NAME = "submit_chat_turn"


def get_llm_provider() -> str:
    return os.getenv("LLM_PROVIDER", "anthropic").strip().lower()


def get_anthropic_model() -> str:
    return os.getenv("ANTHROPIC_MODEL", DEFAULT_ANTHROPIC_MODEL)


def get_openai_model() -> str:
    return os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)


def load_system_prompt() -> str:
    if not SYSTEM_PROMPT_PATH.is_file():
        raise FileNotFoundError(f"System prompt not found: {SYSTEM_PROMPT_PATH}")
    return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")


def get_anthropic_chat_model() -> str:
    """Chat model used by the decision-tree engine."""
    return os.getenv("ANTHROPIC_CHAT_MODEL", DEFAULT_ANTHROPIC_CHAT_MODEL)


def load_chat_system_prompt() -> str:
    if not CHAT_SYSTEM_PROMPT_PATH.is_file():
        raise FileNotFoundError(f"Decision-tree system prompt not found: {CHAT_SYSTEM_PROMPT_PATH}")
    return CHAT_SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
