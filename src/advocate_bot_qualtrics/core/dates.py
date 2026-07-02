"""Generic date parsing from user free-form text."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import re
from typing import Literal

_ISO_DATE_RE = re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b")
_SLASH_DATE_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")
_MONTH_NAME_DATE_RE = re.compile(
    r"\b("
    r"january|jan|february|feb|march|mar|april|apr|may|june|jun|"
    r"july|jul|august|aug|september|sep|sept|october|oct|november|nov|december|dec"
    r")\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b",
    re.IGNORECASE,
)
_MONTH_YEAR_RE = re.compile(
    r"\b(?:around|roughly|about|approximately|approx\.?\s+)?("
    r"january|jan|february|feb|march|mar|april|apr|may|june|jun|"
    r"july|jul|august|aug|september|sep|sept|october|oct|november|nov|december|dec"
    r")\.?,?\s+(\d{4})\b",
    re.IGNORECASE,
)
_RELATIVE_YEAR_BEFORE_RE = re.compile(
    r"\b(?:about|around|roughly|approximately|approx\.?\s+)?"
    r"(?:(\d{1,2})\s+months?|a\s+year|one\s+year|twelve\s+months)"
    r"\s+before\s+(?:the\s+)?(?:complaint(?:\s+was)?\s+filed|filing)\b",
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


@dataclass(frozen=True)
class ParsedDate:
    value: date
    approximate: bool
    source: Literal["exact", "month_year", "relative_to_anchor"]


def parse_submitted_date(text: str) -> date | None:
    """Extract the most recent exact date from free-form user text."""
    candidates = _find_dates_in_text(text)
    return max(candidates) if candidates else None


def parse_user_date(text: str, *, anchor_date: date | None = None) -> ParsedDate | None:
    """Extract an exact or approximate date from free-form user text."""
    exact = parse_submitted_date(text)
    if exact is not None:
        return ParsedDate(value=exact, approximate=False, source="exact")

    month_year = _find_month_year_date(text)
    if month_year is not None:
        return ParsedDate(value=month_year, approximate=True, source="month_year")

    relative = _find_relative_anchor_date(text, anchor_date=anchor_date)
    if relative is not None:
        return ParsedDate(value=relative, approximate=True, source="relative_to_anchor")

    return None


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


def _find_month_year_date(text: str) -> date | None:
    match = _MONTH_YEAR_RE.search(text)
    if not match:
        return None
    month = _MONTH_BY_NAME[match.group(1).lower()]
    year = int(match.group(2))
    return _safe_date(year, month, 15)


def _find_relative_anchor_date(text: str, *, anchor_date: date | None) -> date | None:
    if anchor_date is None:
        return None
    match = _RELATIVE_YEAR_BEFORE_RE.search(text)
    if not match:
        return None
    months = 12
    if match.group(1):
        months = int(match.group(1))
    approx_target = anchor_date - timedelta(days=round(months * 365 / 12))
    return _safe_date(approx_target.year, approx_target.month, 15)


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None
