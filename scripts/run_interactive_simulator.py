#!/usr/bin/env python3
"""CLI for role-playing simulator runs against the interactive decision tree."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_persona_text(*, persona: str | None, persona_file: Path | None) -> str:
    parts: list[str] = []
    if persona_file is not None:
        parts.append(persona_file.read_text(encoding="utf-8").strip())
    if persona:
        parts.append(persona.strip())
    return "\n\n".join(part for part in parts if part)


def _load_personas_from_dir(persona_dir: Path) -> list[tuple[str, str, str]]:
    personas: list[tuple[str, str, str]] = []
    for path in sorted(persona_dir.iterdir()):
        if path.suffix.lower() not in {".md", ".txt"}:
            continue
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            continue
        slug = path.stem
        personas.append((slug, text, str(path)))
    return personas


def _build_persona_list(args: argparse.Namespace) -> list[tuple[str, str, str]]:
    from advocate_bot_qualtrics.simulator.run import slugify_persona

    if args.persona_dir is not None:
        personas = _load_personas_from_dir(args.persona_dir)
        if not personas:
            raise SystemExit(f"No persona files found in {args.persona_dir}")
        return personas

    text = _load_persona_text(persona=args.persona, persona_file=args.persona_file)
    if not text:
        raise SystemExit("Provide --persona, --persona-file, or --persona-dir.")
    slug = slugify_persona(text[:80], fallback="persona")
    if args.persona_file is not None:
        slug = args.persona_file.stem
    source = str(args.persona_file) if args.persona_file else "cli"
    return [(slug, text, source)]


def _print_summary(results) -> int:
    exit_code = 0
    print(f"\nCompleted {len(results)} simulation run(s):\n")
    for result in results:
        status = result.status.value
        if status not in {"complete"}:
            exit_code = 1
        print(f"- [{status}] {result.config.persona_slug} run {result.config.run_index}")
        print(f"  transcript: {result.transcript_path}")
        if result.json_path:
            print(f"  json:       {result.json_path}")
        if result.excel_path:
            print(f"  excel:      {result.excel_path}")
        if result.stall_reason:
            print(f"  stall:      {result.stall_reason}")
        if result.error_message:
            print(f"  error:      {result.error_message}")
        print(f"  turns:      {len(result.turn_records)}")
    return exit_code


def main() -> int:
    from advocate_bot_qualtrics.simulator.config import (
        DEFAULT_FACTS_JSON,
        DEFAULT_MAX_TURNS,
        DEFAULT_OUTPUT_DIR,
        DEFAULT_QA_TURNS,
        DEFAULT_REPEAT,
        DEFAULT_SESSION_FIELDS_XLSX,
        DEFAULT_STALL_TURNS,
    )
    from advocate_bot_qualtrics.simulator.run import run_batch
    from advocate_bot_qualtrics.simulator.schemas import BatchConfig

    parser = argparse.ArgumentParser(
        description="Run a role-playing simulator against the interactive decision tree."
    )
    parser.add_argument(
        "--facts-json",
        type=Path,
        default=DEFAULT_FACTS_JSON,
        help="Path to ComplaintFactSheet JSON",
    )
    parser.add_argument("--persona", default=None, help="Inline role-play instructions")
    parser.add_argument("--persona-file", type=Path, default=None, help="Persona text file")
    parser.add_argument(
        "--persona-dir",
        type=Path,
        default=None,
        help="Directory of persona .md/.txt files for batch runs",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Transcript path for a single run (ignored when batching multiple personas)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for batch transcript files",
    )
    parser.add_argument(
        "--session-fields-xlsx",
        type=Path,
        default=DEFAULT_SESSION_FIELDS_XLSX,
        help="Excel workbook for simulator session field exports",
    )
    parser.add_argument("--max-turns", type=int, default=DEFAULT_MAX_TURNS)
    parser.add_argument("--stall-turns", type=int, default=DEFAULT_STALL_TURNS)
    parser.add_argument("--qa-turns", type=int, default=DEFAULT_QA_TURNS)
    parser.add_argument("--repeat", type=int, default=DEFAULT_REPEAT)
    parser.add_argument("--json", action="store_true", help="Also write JSON sidecar per run")
    args = parser.parse_args()

    if args.repeat < 1:
        print("--repeat must be at least 1", file=sys.stderr)
        return 2

    try:
        personas = _build_persona_list(args)
    except SystemExit as exc:
        print(exc, file=sys.stderr)
        return 2

    is_single = len(personas) == 1 and args.repeat == 1
    batch = BatchConfig(
        facts_path=args.facts_json.resolve(),
        personas=personas,
        session_fields_xlsx=args.session_fields_xlsx.resolve(),
        output_dir=args.output_dir.resolve(),
        max_turns=args.max_turns,
        stall_turns=args.stall_turns,
        qa_turns=args.qa_turns,
        repeat=args.repeat,
        write_json=args.json,
        batch_timestamp=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
    )

    if is_single and args.output is not None:
        from advocate_bot_qualtrics.fact_sheet_io import load_complaint_fact_sheet
        from advocate_bot_qualtrics.simulator.run import run_single_simulation
        from advocate_bot_qualtrics.simulator.schemas import SimulationConfig

        slug, text, _source = personas[0]
        config = SimulationConfig(
            facts=load_complaint_fact_sheet(batch.facts_path),
            facts_path=batch.facts_path,
            persona=text,
            persona_slug=slug,
            session_fields_xlsx=batch.session_fields_xlsx,
            output_path=args.output.resolve(),
            max_turns=batch.max_turns,
            stall_turns=batch.stall_turns,
            qa_turns=batch.qa_turns,
            write_json=batch.write_json,
            run_index=1,
            batch_timestamp=batch.batch_timestamp,
        )
        results = [run_single_simulation(config)]
    else:
        results = run_batch(batch)

    return _print_summary(results)


if __name__ == "__main__":
    raise SystemExit(main())
