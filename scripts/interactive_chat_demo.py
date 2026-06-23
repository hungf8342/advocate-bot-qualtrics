#!/usr/bin/env python3
"""Browser demo for the interactive decision tree (Gradio)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FACTS = PROJECT_ROOT / "fixtures" / "complaint_fact_sheet.sample.json"


def _format_debug(snapshot: dict) -> str:
    return f"""### Session debug

- **Facts file:** `{snapshot.get("facts_path") or "—"}`
- **Current node:** `{snapshot.get("current_node_id")}`
- **Status:** {snapshot.get("tree_status")}

**SOL dates**
- Filing: {snapshot.get("filing_date")}
- Last payment (complaint): {snapshot.get("last_payment_complaint")}
- Last payment (OG creditor): {snapshot.get("last_payment_og_creditor")}
- Last payment (debt collector): {snapshot.get("last_payment_debt_collector")}
- Filing date changed from extraction: {snapshot.get("filing_date_changed")}
- Last payment date changed from extraction: {snapshot.get("last_payment_date_changed")}

**FDCPA flags**
- Threatened: {snapshot.get("threatened")}
- Disclosed to third parties: {snapshot.get("disclosed")}
- Evidence: {snapshot.get("evidence")}

**Hook outcomes**
- SOL: {snapshot.get("sol_outcome")}
- FDCPA: {snapshot.get("fdcpa_outcome")}

**Node answers (confidence)**
{_format_node_answers(snapshot.get("node_answers") or {})}

**Excel export**
- Session fields: `{snapshot.get("session_fields_xlsx") or "—"}`
"""


def _format_node_answers(node_answers: dict) -> str:
    if not node_answers:
        return "- (none yet)"
    lines = []
    for node_id, record in node_answers.items():
        skipped = " skipped" if record.get("skipped") else ""
        lines.append(
            f"- `{node_id}`: {record.get('branch')} @ {record.get('confidence_pct')}%{skipped}"
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--facts-json",
        type=Path,
        default=DEFAULT_FACTS,
        help="Path to ComplaintFactSheet JSON",
    )
    parser.add_argument(
        "--practice-area",
        default="consumer_debt",
        help="Practice area bundle id (default: consumer_debt)",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7860)
    parser.add_argument(
        "--share",
        action="store_true",
        help="Create a public Gradio link (dev demos only; do not use with real client data)",
    )
    args = parser.parse_args()

    try:
        import gradio as gr
    except ImportError:
        print("Gradio is not installed. Run: pip install -e '.[demo]'", file=sys.stderr)
        return 1

    from advocate_bot_qualtrics.core.bundle import get_bundle
    from advocate_bot_qualtrics.decision_tree.interactive_host import InteractiveChatEngine

    bundle = get_bundle(args.practice_area)
    facts_path = str(args.facts_json.resolve())
    facts = bundle.load_facts(args.facts_json)
    engine = InteractiveChatEngine.from_fact_sheet(
        facts, practice_area_id=args.practice_area
    )

    def _chat_history() -> list[dict[str, str]]:
        return [{"role": role, "content": text} for role, text in engine.transcript]

    def respond(user_message: str, history: list[dict[str, str]]):
        if not user_message.strip():
            return history, "", _format_debug(engine.debug_snapshot(facts_path=facts_path))

        step = engine.submit(user_message)
        history = _chat_history()
        if step.error:
            history = history + [{"role": "assistant", "content": f"Error: {step.error}"}]
        return history, "", _format_debug(engine.debug_snapshot(facts_path=facts_path))

    def reset_session():
        engine.reset()
        history = [{"role": "assistant", "content": msg} for msg in engine.initial_messages()]
        return history, "", _format_debug(engine.debug_snapshot(facts_path=facts_path))

    def reload_facts(upload_path: str | None):
        nonlocal facts, facts_path
        if not upload_path:
            return (
                _chat_history(),
                "",
                _format_debug(engine.debug_snapshot(facts_path=facts_path)),
            )
        try:
            data = json.loads(Path(upload_path).read_text(encoding="utf-8"))
            facts = type(facts).model_validate(data)
            facts_path = str(Path(upload_path).resolve())
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            history = _chat_history() + [
                {"role": "assistant", "content": f"Error: invalid facts file: {exc}"}
            ]
            return history, "", _format_debug(engine.debug_snapshot(facts_path=facts_path))

        engine.facts = facts
        messages = engine.reset()
        history = [{"role": "assistant", "content": msg} for msg in messages]
        return history, "", _format_debug(engine.debug_snapshot(facts_path=facts_path))

    with gr.Blocks(title="Interactive decision tree demo") as demo:
        gr.Markdown(
            "# Interactive decision tree demo\n"
            "Live chat against the SOL → FDCPA interactive tree using pre-extracted complaint facts."
        )
        with gr.Row():
            with gr.Column(scale=3):
                chatbot = gr.Chatbot(label="Chat", height=480)
                user_input = gr.Textbox(
                    label="Your message",
                    placeholder="Type your answer or ask about the complaint…",
                )
                with gr.Row():
                    send = gr.Button("Send", variant="primary")
                    reset_btn = gr.Button("Reset")
            with gr.Column(scale=1):
                debug_panel = gr.Markdown(_format_debug(engine.debug_snapshot(facts_path=facts_path)))
                facts_upload = gr.File(label="Reload facts JSON", file_types=[".json"])

        initial = [{"role": "assistant", "content": msg} for msg in engine.initial_messages()]
        demo.load(
            lambda: (initial, "", _format_debug(engine.debug_snapshot(facts_path=facts_path))),
            outputs=[chatbot, user_input, debug_panel],
        )

        send.click(respond, inputs=[user_input, chatbot], outputs=[chatbot, user_input, debug_panel])
        user_input.submit(
            respond, inputs=[user_input, chatbot], outputs=[chatbot, user_input, debug_panel]
        )
        reset_btn.click(reset_session, outputs=[chatbot, user_input, debug_panel])
        facts_upload.change(reload_facts, inputs=[facts_upload], outputs=[chatbot, user_input, debug_panel])

    demo.launch(server_name=args.host, server_port=args.port, share=args.share)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
