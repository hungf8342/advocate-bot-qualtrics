"""Load ComplaintFactSheet JSON for downstream decision trees."""

from __future__ import annotations

import json
from pathlib import Path

from advocate_bot_qualtrics.schemas.complaint_fact_sheet import ComplaintFactSheet

DEFAULT_FIXTURE = (
    Path(__file__).resolve().parents[2] / "fixtures" / "complaint_fact_sheet.sample.json"
)


def load_complaint_fact_sheet(path: Path | str) -> ComplaintFactSheet:
    """Load and validate a ComplaintFactSheet from a JSON file."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return ComplaintFactSheet.model_validate(data)
