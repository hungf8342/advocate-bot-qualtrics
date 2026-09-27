#!/usr/bin/env python3
"""Browser demo for the interactive decision tree (Gradio)."""

from __future__ import annotations

import argparse
from html import escape
import re
import sys
from pathlib import Path
from urllib.parse import quote

PROJECT_ROOT = Path(__file__).resolve().parents[1]

INTERFACE_CSS = (PROJECT_ROOT / "scripts/assets/debt_chat.css").read_text(encoding="utf-8")

FIELD_LABELS = {
    "PLAINTIFF-NAME": "Who is suing you",
    "PLAINTIFF": "Type of plaintiff",
    "RECOGNIZE": "Do you recognize the account?",
    "AMOUNT": "Amount claimed / your correction",
    "LAW-FIRM": "Plaintiff’s law firm",
    "SUIT-TYPE": "Type of claim",
    "ORAL": "Oral agreement only?",
    "LAST-PAYMENT-DATE": "Last payment date",
    "OPEN-DATE": "Account opening date",
    "STATEMENT": "Statement attached?",
    "OWNERSHIP": "Ownership documents attached?",
    "VERIFIED": "Complaint verified?",
    "CONSOLIDATION": "Using a debt consolidation company?",
}
CHOICE_LABELS = {
    "yes": "Yes", "no": "No", "original": "Original creditor", "buyer": "Debt buyer",
    "breach": "Breach of contract", "common": "Common counts", "both": "Breach of contract and common counts",
}


def _case_details(snapshot: dict) -> str:
    """Render escaped, session-backed values; never scrape the transcript."""
    fields = snapshot.get("preliminary_fields") or {}
    rows = []
    for index, (tag, label) in enumerate(FIELD_LABELS.items()):
        entry = fields.get(tag)
        if entry is None and index >= 5:
            continue
        value = entry.get("value") if entry else None
        if value is None:
            status = entry.get("status") if entry else None
            display = "Not stated in complaint" if status == "missing" else "Not sure" if entry else "Not answered yet"
        else:
            display = CHOICE_LABELS.get(str(value), str(value)) if tag not in {"PLAINTIFF-NAME", "LAW-FIRM", "AMOUNT"} else str(value)
        note = ""
        if entry and entry.get("disputed"):
            original = entry.get("complaint_value")
            note = f'<small class="correction-note">Your correction · Complaint: {escape(str(original))}</small>'
        rows.append(f'<div class="field"><dt>{escape(label)}</dt><dd class="{"empty" if value is None else ""}">{escape(display)}{note}</dd></div>')
    card = (
        '<div class="case-card"><p class="eyebrow">For your reference</p><h2>Your case details</h2>'
        '<p class="aside-intro">These are the answers collected so far. You can refer to them as you go.</p>'
        f'<dl>{"".join(rows)}</dl><div class="aside-foot">This is a recap of your answers, '
        'not a conclusion about your case.</div></div>'
    )
    return f'<div class="desktop-details">{card}</div><details class="mobile-summary"><summary>Your case details</summary>{card}</details>'


def _chat_history(engine) -> list[dict[str, str]]:
    tree = getattr(getattr(engine, "bundle", None), "tree", None)
    asset_urls = {
        image.path: "/gradio_api/file=" + quote(str((PROJECT_ROOT / image.path).resolve()), safe="/")
        for node in (tree.nodes if tree is not None else [])
        if node.explanation is not None
        for image in node.explanation.images
    }

    def display(role: str, message: str) -> str:
        if role != "assistant":
            return message
        message = re.sub(r"\s*\[[A-Z][A-Z0-9-]*\]", "", message)
        for path, url in asset_urls.items():
            message = message.replace(f"]({path})", f"]({url})")
        return message

    return [
        {"role": role, "content": display(role, text)}
        for role, text in engine.transcript
    ]


def _format_debug(snapshot: dict) -> str:
    return f"""### Session debug

- **Current node:** `{snapshot.get("current_node_id")}`
- **Status:** {snapshot.get("tree_status")}

**SOL dates**
- Filing: {snapshot.get("filing_date")}
- Last payment (complaint): {snapshot.get("last_payment_complaint")}
- Last payment (OG creditor): {snapshot.get("last_payment_og_creditor")}
- Last payment (debt collector): {snapshot.get("last_payment_debt_collector")}

**Defense results**
{chr(10).join(f'- `{defense}`: {result["status"]}' for defense, result in (snapshot.get("defense_results") or {}).items()) or '- (none yet)'}

**Preliminary fields**
{_format_preliminary_fields(snapshot.get("preliminary_fields") or {})}

**Reused answers**
{chr(10).join(f'- `{node}` ← `{source}`' for node, source in (snapshot.get("reused_answers") or {}).items()) or '- (none yet)'}

**Node answers (confidence)**
{_format_node_answers(snapshot.get("node_answers") or {})}

**Excel export**
- Session fields: `{snapshot.get("session_fields_xlsx") or "—"}`
"""


def _format_preliminary_fields(fields: dict) -> str:
    lines = []
    for tag, entry in fields.items():
        value = entry.get("value")
        display = str(value) if value is not None else entry.get("status", "unknown")
        if entry.get("disputed"):
            display += f" (corrected/disputed; complaint: {entry.get('complaint_value')})"
        lines.append(f"- `[{tag}]`: {display}")
    return "\n".join(lines) or "- (none yet)"


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

    from advocate_bot_qualtrics.decision_tree.interactive_host import InteractiveChatEngine

    def outputs_for(engine, error=None, draft=""):
        snapshot = engine.debug_snapshot()
        history = _chat_history(engine)
        if error:
            history.append({"role": "assistant", "content": f"Error: {error}"})
        status = "Review complete · Questions welcome" if engine.tree_complete else "Conversation in progress"
        heading = f'<div class="chat-heading"><span class="status-dot" aria-hidden="true"></span>{status}</div>'
        return history, draft, _case_details(snapshot), _format_debug(snapshot), heading, engine

    def new_session():
        engine = InteractiveChatEngine.from_user_input(practice_area_id=args.practice_area)
        engine.initial_messages()
        return outputs_for(engine)

    def respond(user_message, engine):
        if engine is None:
            engine = InteractiveChatEngine.from_user_input(practice_area_id=args.practice_area)
            engine.initial_messages()
        if not user_message.strip():
            return outputs_for(engine)
        step = engine.submit(user_message)
        return outputs_for(engine, step.error, user_message if step.error else "")

    with gr.Blocks(title="Debt case guide") as demo:
        engine_state = gr.State(None)
        with gr.Column(elem_id="app-shell"):
            gr.HTML('<header class="topbar"><div class="top-inner"><div class="brand"><span class="mark" aria-hidden="true">✦</span> Debt case guide</div><div class="top-note">A step-by-step conversation about your case</div></div></header>', elem_id="site-header")
            with gr.Row(elem_id="main-layout"):
                with gr.Column(elem_id="conversation"):
                    gr.HTML('<h1>Let’s understand your case</h1><p class="intro">Answer one question at a time. You can use the case details beside the conversation to check what you’ve told us.</p>', elem_id="intro")
                    with gr.Column(elem_id="chat-card"):
                        chat_heading = gr.HTML('<div class="chat-heading"><span class="status-dot" aria-hidden="true"></span>Conversation in progress</div>')
                        chatbot = gr.Chatbot(show_label=False, height=450, layout="bubble", buttons=[], elem_id="chat-messages")
                        with gr.Column(elem_id="composer"):
                            with gr.Row(elem_id="composer-inner"):
                                user_input = gr.Textbox(label="Your answer", show_label=False, placeholder="Type your answer…", container=False, lines=1, max_lines=4, scale=12, elem_id="answer")
                                send = gr.Button("Send", variant="primary", elem_id="send-button", scale=0, min_width=76)
                            gr.HTML('<p class="composer-note">Share only what you’re comfortable entering. This prototype does not upload files.</p>')
                with gr.Column(elem_id="sidebar"):
                    case_details = gr.HTML(_case_details({}), elem_id="case-details")
                    with gr.Accordion("Developer view", open=True, elem_id="debug"):
                        debug_panel = gr.Markdown()
                        reset_btn = gr.Button("Start a new session", size="sm", elem_id="reset-session")

        outputs = [chatbot, user_input, case_details, debug_panel, chat_heading, engine_state]
        demo.load(new_session, outputs=outputs)
        send.click(respond, inputs=[user_input, engine_state], outputs=outputs, concurrency_limit=1, concurrency_id="chat")
        user_input.submit(respond, inputs=[user_input, engine_state], outputs=outputs, concurrency_limit=1, concurrency_id="chat")
        reset_btn.click(new_session, outputs=outputs, concurrency_limit=1, concurrency_id="chat")

    demo.launch(
        server_name=args.host,
        server_port=args.port,
        share=args.share,
        debug=True,
        css=INTERFACE_CSS,
        allowed_paths=[str(PROJECT_ROOT / "complaint-examples")],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
