"""Generic date parsing from user free-form text."""

from __future__ import annotations

import re
from datetime import date

_ISO_DATE_RE = re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b")
_SLASH_DATE_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")
_MONTH_NAME_DATE_RE = re.compile(
    r"\b("
    r"january|jan|february|feb|march|mar|april|apr|may|june|jun|"
    r"july|jul|august|aug|september|sep|sept|october|oct|november|nov|december|dec"
    r")\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b",
    re.IGNORECASE,
)
_MONTH_BY_NAME = {
    "january": 1,
    "jan": 1,
    "february": 2,
    "feb": 2,
    "march": 3,
    "mar": 3,
    "april": 4,
    "apr": 4,
    "may": 5,
    "june": 6,
    "jun": 6,
    "july": 7,
    "jul": 7,
    "august": 8,
    "aug": 8,
    "september": 9,
    "sep": 9,
    "sept": 9,
    "october": 10,
    "oct": 10,
    "november": 11,
    "nov": 11,
    "december": 12,
    "dec": 12,
}


def parse_submitted_date(text: str) -> date | None:
    """Extract the most recent plausible date from free-form user text."""
    candidates = _find_dates_in_text(text)
    return max(candidates) if candidates else None


def _find_dates_in_text(text: str) -> list[date]:
    found: list[date] = []
    for match in _ISO_DATE_RE.finditer(text):
        parsed = _safe_date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        if parsed:
            found.append(parsed)
    for match in _SLASH_DATE_RE.finditer(text):
        parsed = _safe_date(int(match.group(3)), int(match.group(1)), int(match.group(2)))
        if parsed:
            found.append(parsed)
    for match in _MONTH_NAME_DATE_RE.finditer(text):
        month = _MONTH_BY_NAME[match.group(1).lower()]
        parsed = _safe_date(int(match.group(3)), month, int(match.group(2)))
        if parsed:
            found.append(parsed)
    return found


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None
