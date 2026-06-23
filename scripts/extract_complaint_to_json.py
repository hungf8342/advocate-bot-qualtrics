#!/usr/bin/env python3
"""Extract ComplaintFactSheet from complaint text/PDF and write JSON."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PDF = PROJECT_ROOT / "knowledge-base" / "1 - Complaint.pdf"
DEFAULT_OUTPUT = PROJECT_ROOT / "output" / "complaint_fact_sheet.json"


def _read_input(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(path)
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    return path.read_text(encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "input",
        nargs="?",
        type=Path,
        default=DEFAULT_PDF,
        help="Complaint .pdf or .txt (default: knowledge-base sample PDF)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Output JSON path",
    )
    parser.add_argument(
        "--practice-area",
        default="consumer_debt",
        help="Practice area bundle id (default: consumer_debt)",
    )
    parser.add_argument(
        "--provider",
        choices=("anthropic", "openai"),
        default=None,
        help="LLM provider override",
    )
    args = parser.parse_args()

    if not args.input.is_file():
        print(f"Input not found: {args.input}", file=sys.stderr)
        return 1

    raw_text = _read_input(args.input).strip()
    if not raw_text:
        print(f"No text extracted from: {args.input}", file=sys.stderr)
        return 1

    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env")

    import os

    from advocate_bot_qualtrics import extract_complaint_facts
    from advocate_bot_qualtrics.config import get_llm_provider
    from advocate_bot_qualtrics.core.bundle import get_bundle

    provider = args.provider or get_llm_provider()
    if provider == "anthropic" and not os.getenv("ANTHROPIC_API_KEY"):
        print(
            "Missing ANTHROPIC_API_KEY. Copy .env.example to .env and set your Anthropic key.",
            file=sys.stderr,
        )
        return 1
    if provider == "openai" and not os.getenv("OPENAI_API_KEY"):
        print(
            "Missing OPENAI_API_KEY. Copy .env.example to .env and set your key.",
            file=sys.stderr,
        )
        return 1

    from advocate_bot_qualtrics.core.bundle import get_bundle

    get_bundle(args.practice_area)

    facts = extract_complaint_facts(raw_text, provider=provider)
    payload = facts.model_dump(mode="json")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
