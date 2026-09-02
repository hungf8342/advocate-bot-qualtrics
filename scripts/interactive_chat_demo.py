#!/usr/bin/env python3
"""Browser demo for the interactive decision tree (Gradio)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

CHATGPT_LIKE_CSS = """
body, .gradio-container { background: #ffffff !important; }
.gradio-container { max-width: none !important; padding: 0 !important; font-family: Inter, ui-sans-serif, system-ui, sans-serif !important; }
#app-shell { min-height: 100vh; }
#topbar { height: 56px; border-bottom: 1px solid #e5e5e5; padding: 0 22px; display: flex; align-items: center; }
#brand { font-size: 16px; font-weight: 650; color: #202123; }
#conversation { max-width: 760px; margin: 0 auto; padding: 26px 20px 160px; }
#conversation .message-wrap { border: 0 !important; }
#conversation .message { font-size: 15px; line-height: 1.55; }
#composer { position: fixed; z-index: 5; bottom: 0; left: 0; right: 0; padding: 14px 20px 24px; background: linear-gradient(transparent, #fff 35%); }
#composer-inner { max-width: 760px; margin: 0 auto; border: 1px solid #d9d9e3; border-radius: 24px; box-shadow: 0 2px 10px rgba(0,0,0,.08); padding: 5px 8px 5px 16px; background: #fff; }
#composer-inner textarea { border: 0 !important; box-shadow: none !important; min-height: 38px !important; }
#send-button { border-radius: 18px !important; min-width: 38px !important; }
.suggestion-row { max-width: 760px; margin: 0 auto 10px; gap: 8px; }
.suggestion-row button { border-radius: 18px !important; border: 1px solid #d9d9e3 !important; background: #fff !important; color: #353740 !important; font-size: 13px !important; }
#debug { position: fixed; right: 18px; top: 72px; width: 290px; max-height: calc(100vh - 90px); overflow: auto; border: 1px solid #e5e5e5; border-radius: 12px; padding: 12px; background: #fff; box-shadow: 0 4px 18px rgba(0,0,0,.08); }
@media (max-width: 1050px) { #debug { position: static; width: auto; max-width: 760px; margin: 0 auto 120px; } #composer { position: static; padding: 0 20px 24px; } #conversation { padding-bottom: 18px; } }
"""


def _format_debug(snapshot: dict) -> str:
    return f"""### Session debug

- **Current node:** `{snapshot.get("current_node_id")}`
- **Status:** {snapshot.get("tree_status")}

**SOL dates**
- Filing: {snapshot.get("filing_date")}
- Last payment (complaint): {snapshot.get("last_payment_complaint")}
- Last payment (OG creditor): {snapshot.get("last_payment_og_creditor")}
- Last payment (debt collector): {snapshot.get("last_payment_debt_collector")}

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
    engine = InteractiveChatEngine.from_user_input(practice_area_id=args.practice_area)

    def _chat_history() -> list[dict[str, str]]:
        return [{"role": role, "content": text} for role, text in engine.transcript]

    def suggestions() -> list[str]:
        definition = bundle.tree.node(engine.current_node_id)
        if definition.kind == "choice":
            return [branch.label for branch in definition.branches]
        if definition.input and definition.input.unknown_branch_id:
            return ["I don't know"]
        return []

    def suggestion_updates(values: list[str]):
        padded = values[:3] + [""] * (3 - len(values[:3]))
        return [gr.update(value=value, visible=bool(value)) for value in padded]

    def response_outputs(user_message: str, history: list[dict[str, str]]):
        if not user_message.strip():
            return (history, "", _format_debug(engine.debug_snapshot()), suggestions(), *suggestion_updates(suggestions()))

        step = engine.submit(user_message)
        history = _chat_history()
        if step.error:
            history = history + [{"role": "assistant", "content": f"Error: {step.error}"}]
        choices = suggestions()
        return history, "", _format_debug(engine.debug_snapshot()), choices, *suggestion_updates(choices)

    def respond(user_message: str, history: list[dict[str, str]]):
        return response_outputs(user_message, history)

    def respond_suggestion(index: int, values: list[str], history: list[dict[str, str]]):
        return response_outputs(values[index] if index < len(values) else "", history)

    def reset_session():
        engine.reset()
        history = [{"role": "assistant", "content": msg} for msg in engine.initial_messages()]
        choices = suggestions()
        return history, "", _format_debug(engine.debug_snapshot()), choices, *suggestion_updates(choices)

    with gr.Blocks(title="Advocate Bot") as demo:
        with gr.Column(elem_id="app-shell"):
            gr.HTML('<div id="topbar"><span id="brand">Advocate Bot</span></div>')
            with gr.Column(elem_id="conversation"):
                gr.Markdown("### Consumer-debt screening\nShare only the information you are comfortable entering. No files are uploaded.")
                chatbot = gr.Chatbot(show_label=False, height=520)
            with gr.Column(elem_id="debug"):
                gr.Markdown("#### Developer view")
                debug_panel = gr.Markdown(_format_debug(engine.debug_snapshot()))
                reset_btn = gr.Button("Start a new session", size="sm")
            suggestion_state = gr.State(suggestions())
            with gr.Row(elem_classes=["suggestion-row"]):
                suggestion_one = gr.Button(visible=False, size="sm")
                suggestion_two = gr.Button(visible=False, size="sm")
                suggestion_three = gr.Button(visible=False, size="sm")
            with gr.Column(elem_id="composer"):
                with gr.Row(elem_id="composer-inner"):
                    user_input = gr.Textbox(show_label=False, placeholder="Message Advocate Bot…", container=False, scale=12)
                    send = gr.Button("↑", variant="primary", elem_id="send-button", scale=1)

        initial = [{"role": "assistant", "content": msg} for msg in engine.initial_messages()]
        demo.load(
            lambda: (initial, "", _format_debug(engine.debug_snapshot()), suggestions(), *suggestion_updates(suggestions())),
            outputs=[chatbot, user_input, debug_panel, suggestion_state, suggestion_one, suggestion_two, suggestion_three],
        )

        outputs = [chatbot, user_input, debug_panel, suggestion_state, suggestion_one, suggestion_two, suggestion_three]
        send.click(respond, inputs=[user_input, chatbot], outputs=outputs)
        user_input.submit(
            respond, inputs=[user_input, chatbot], outputs=outputs
        )
        reset_btn.click(reset_session, outputs=outputs)
        suggestion_one.click(lambda values, history: respond_suggestion(0, values, history), inputs=[suggestion_state, chatbot], outputs=outputs)
        suggestion_two.click(lambda values, history: respond_suggestion(1, values, history), inputs=[suggestion_state, chatbot], outputs=outputs)
        suggestion_three.click(lambda values, history: respond_suggestion(2, values, history), inputs=[suggestion_state, chatbot], outputs=outputs)

    demo.launch(
        server_name=args.host,
        server_port=args.port,
        share=args.share,
        debug=True,
        css=CHATGPT_LIKE_CSS,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
