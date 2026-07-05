"""Confidence scoring helpers for interactive decision-tree chat."""

from __future__ import annotations

import re

HEDGE_CLAMP_MAX = 70

_PURE_IDK_RE = re.compile(
    r"\b("
    r"i don'?t know|don't know|no idea|not sure|unsure|can't tell|cant tell|no clue"
    r")\b",
    re.IGNORECASE,
)
_LEAN_YES_RE = re.compile(
    r"\b(yes|yeah|yep|yup|correct|right|true|affirmative)\b",
    re.IGNORECASE,
)
_LEAN_NO_RE = re.compile(r"\b(no|nope|nah|negative|wrong|incorrect|false)\b", re.IGNORECASE)
_LEAN_BUT_RE = re.compile(
    r"\bbut\s+(yes|no|yeah|nope|probably|say)\b",
    re.IGNORECASE,
)
_LETS_SAY_RE = re.compile(r"\blet'?s\s+say\b", re.IGNORECASE)
_HEDGE_CLAMP_RE = re.compile(r"\b(think|maybe|not sure)\b", re.IGNORECASE)
_LATEST_USER_MESSAGE_RE = re.compile(
    r"Latest user message:\s*\nUser:\s*(.+)\Z",
    re.DOTALL,
)
_IDK_STRIP_FOR_NO = (
    "no idea",
    "not sure",
    "don't know",
    "i don't know",
    "i dont know",
)
_BARE_IDK_ABSTENTION_PHRASES = frozenset(
    {
        "i dont know",
        "dont know",
        "no idea",
        "not sure",
        "im not sure",
        "unsure",
        "cant tell",
        "no clue",
    }
)
_NORMALIZE_BARE_ABSTENTION_RE = re.compile(r"[^\w\s]")


def extract_latest_user_message(payload: str) -> str:
    """Pull the latest user line from a host-built chat payload."""
    match = _LATEST_USER_MESSAGE_RE.search(payload.strip())
    if match:
        return match.group(1).strip()
    return payload.strip()


def contains_hedge_words_for_clamp(text: str) -> bool:
    return _HEDGE_CLAMP_RE.search(text) is not None


def clamp_answer_confidence(text: str, confidence_pct: int) -> int:
    """Enforce calibration cap when the user hedges with think/maybe/not sure."""
    if contains_hedge_words_for_clamp(text):
        return min(confidence_pct, HEDGE_CLAMP_MAX)
    return confidence_pct


def _normalize_bare_abstention(text: str) -> str:
    lowered = text.lower().strip().replace("'", "").replace("’", "")
    cleaned = _NORMALIZE_BARE_ABSTENTION_RE.sub(" ", lowered)
    return " ".join(cleaned.split())


def is_bare_idk_abstention(text: str) -> bool:
    """True only for exact bare ignorance phrases eligible for host skip."""
    stripped = text.strip()
    if not stripped or "?" in stripped:
        return False
    return _normalize_bare_abstention(stripped) in _BARE_IDK_ABSTENTION_PHRASES


def has_directional_lean(text: str) -> bool:
    if _LEAN_BUT_RE.search(text) or _LETS_SAY_RE.search(text):
        return True
    if _LEAN_YES_RE.search(text):
        return True
    scrubbed = text.lower()
    for phrase in _IDK_STRIP_FOR_NO:
        scrubbed = scrubbed.replace(phrase, " ")
    if _LEAN_NO_RE.search(scrubbed):
        return True
    return False


def is_pure_idk(text: str) -> bool:
    """True when the user abstains without leaning yes/no."""
    if not _PURE_IDK_RE.search(text):
        return False
    return not has_directional_lean(text)


GENERIC_HEDGE_FALLBACK = (
    "You seemed unsure about that — we'll move forward with what you indicated."
)

_SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.!?])\s+")
_NEXT_QUESTION_RE = re.compile(
    r"\b(what is|what was|please tell|could you|can you|would you|do you know)\b",
    re.IGNORECASE,
)


def to_single_sentence(text: str) -> str:
    """Return the first sentence from text, or the whole string if none found."""
    stripped = text.strip()
    if not stripped:
        return ""
    parts = _SENTENCE_BOUNDARY_RE.split(stripped, maxsplit=1)
    return parts[0].strip()


def had_multiple_sentences(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    first = to_single_sentence(stripped)
    remainder = stripped[len(first) :].strip()
    return bool(remainder) and bool(re.search(r"\w", remainder))


def is_valid_hedge_reply(text: str, *, original: str | None = None) -> bool:
    if not text or len(text) < 10:
        return False
    if text.endswith("?"):
        return False
    if _NEXT_QUESTION_RE.search(text):
        return False
    if original is not None and had_multiple_sentences(original):
        return False
    return True


def resolve_confidence_hedge_message(
    assistant_reply: str,
    *,
    fallback: str = GENERIC_HEDGE_FALLBACK,
) -> str:
    """Prefer a one-sentence LLM hedge; fall back to a generic host template."""
    original = assistant_reply.strip()
    sanitized = to_single_sentence(original)
    if is_valid_hedge_reply(sanitized, original=original):
        return sanitized
    return fallback
