"""Paths and clarification-model configuration for the clickthrough."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parent.parent
PROMPTS_DIR = PROJECT_ROOT / "prompts"

DEFAULT_ZAI_BASE_URL = "https://api.z.ai/api/paas/v4/"
DEFAULT_ZAI_CHAT_MODEL = "glm-5.2"
DEFAULT_CHAT_PROVIDER = "zai"
CHAT_TOOL_NAME = "submit_chat_turn"


def get_chat_provider() -> str:
    """Only Z.ai is supported for the optional clarification chat."""
    return os.getenv("CHAT_PROVIDER", DEFAULT_CHAT_PROVIDER).strip().lower()


def get_zai_api_key() -> str:
    return os.getenv("ZAI_API_KEY", "").strip()


def get_zai_chat_model() -> str:
    return os.getenv("ZAI_CHAT_MODEL", DEFAULT_ZAI_CHAT_MODEL)


def get_zai_base_url() -> str:
    return os.getenv("ZAI_BASE_URL", DEFAULT_ZAI_BASE_URL).strip()
