#!/usr/bin/env python3
"""Run the guided defense prototype: .venv/bin/python scripts/run_clickthrough.py."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Literal
from uuid import UUID

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from advocate_bot_qualtrics.config import PROMPTS_DIR
from advocate_bot_qualtrics.core.schemas import ChatTurnResponse
from advocate_bot_qualtrics.llm.chat_structured import submit_chat_turn
from advocate_bot_qualtrics.practice_areas.consumer_debt.workflow import (
    GuidedAdvanceRequest, GuidedEditRequest, GuidedRequest, ClickthroughReview,
    advance_review, edit_review,
)
from advocate_bot_qualtrics.practice_areas.consumer_debt.research_collection import CollectionContext, ResearchCollection
from advocate_bot_qualtrics.practice_areas.consumer_debt.debug_navigation import jump_to_section

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "scripts/assets/clickthrough"


class HelpMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=5000)


class HelpRequest(GuidedRequest):
    draft_value: str | None = Field(default=None, min_length=1, max_length=300)
    question: str = Field(min_length=1, max_length=1500)
    conversation: list[HelpMessage] = Field(default_factory=list, max_length=12)


class StateRequest(GuidedRequest):
    session_id: UUID | None = None


class AdvanceRequest(GuidedAdvanceRequest):
    collection: CollectionContext | None = None


class EditRequest(GuidedEditRequest):
    collection: CollectionContext | None = None


class DebugJumpRequest(GuidedRequest):
    cursor: int | None = Field(default=None, ge=0, le=400)
    section: str = Field(min_length=1, max_length=100)
    draft_value: str | None = Field(default=None, min_length=1, max_length=300)


class EndRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: UUID


def create_app(complaint_fields: dict | None = None, *, collection_dir: Path | None = None, debug: bool = False) -> FastAPI:
    defaults = dict(complaint_fields or {})
    ClickthroughReview(defaults)  # Fail early on an invalid example input.
    app = FastAPI(title="Debt case guide · Guided defense prototype", docs_url=None, redoc_url=None)
    collection = None if debug else ResearchCollection(collection_dir or ROOT / "output/clickthrough")
    app.state.collection = collection
    app.mount("/assets", StaticFiles(directory=ASSETS), name="assets")

    def review(request: GuidedRequest) -> ClickthroughReview:
        try:
            if request.debug_section is not None and not debug:
                raise ValueError("Section jumping is available only in debug mode.")
            if request.revision:
                ClickthroughReview(defaults, debug_section=request.debug_section).replay(request.revision.previous_history)
            current = ClickthroughReview(defaults, debug_section=request.debug_section).replay(request.history)
            current.revision = request.revision
            return current
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/")
    def index():
        html = (ASSETS / "index.html").read_text(encoding="utf-8")
        version = hashlib.sha256(b"".join((ASSETS / name).read_bytes()
                                         for name in ("app.js", "style.css"))).hexdigest()[:12]
        for name in ("app.js", "style.css"):
            html = html.replace(f'"/assets/{name}"', f'"/assets/{name}?v={version}"')
        if debug:
            html = html.replace("<body>", '<body data-debug-mode="true">')
        return HTMLResponse(html, headers={"Cache-Control": "no-store"})

    def page_for(current):
        page = current.page()
        if debug and page["input_type"] == "complete":
            page["title"] = "Debug run complete"
            page["body"] = ["Sections skipped using header links were not reviewed. Click a header to inspect another section."]
        return page

    @app.post("/api/state")
    def state(request: StateRequest):
        page = page_for(review(request))
        if request.session_id and collection is not None:
            collection.start(request.session_id)
        return page

    @app.post("/api/collection/end")
    def end_session(request: EndRequest):
        if collection is None:
            return {"saved": False, "debug_mode": True}
        try:
            collection.end(request.session_id)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {"saved": True}

    def workflow_result(current: ClickthroughReview):
        return {"history": [a.model_dump(mode="json") for a in current.history],
                "revision": current.revision.model_dump(mode="json") if current.revision else None,
                "debug_section": current.debug_section,
                "page": page_for(current)}

    @app.post("/api/edit")
    def edit(request: EditRequest):
        review(request)
        try:
            current = edit_review(defaults, request)
            if request.collection and collection is not None:
                collection.record(request.collection, current, request.history[request.edit_index].node_id, request.value)
            return workflow_result(current)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/advance")
    def advance(request: AdvanceRequest):
        previous = review(request)
        try:
            current = advance_review(defaults, request)
            if request.collection and collection is not None:
                collection.record(request.collection, current, previous.current, request.value)
            return workflow_result(current)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/debug/jump")
    def debug_jump(request: DebugJumpRequest):
        if not debug:
            raise HTTPException(status_code=404, detail="Debug navigation is disabled.")
        current = review(request)
        try:
            active = current
            if request.cursor is not None:
                if request.cursor > len(request.history):
                    raise ValueError("Choose an existing position in the review.")
                active = review(request.model_copy(update={"history": request.history[:request.cursor]}))
            return workflow_result(jump_to_section(current, request.section, request.draft_value, draft_node=active.current))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/preview")
    def preview(request: GuidedAdvanceRequest):
        current = review(request)
        try:
            return {"node_id": current.current, **current.preview_formatted_response(request.value)}
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/help")
    def help_chat(request: HelpRequest):
        current = review(request)
        question = request.question.strip()
        if not question:
            raise HTTPException(status_code=422, detail="Enter a question first.")
        payload = {
            "current_node": current.chat_node().model_dump(),
            "confirmed_case_facts": current.case_details(),
            "conversation": [m.model_dump() for m in request.conversation],
            "user_message": question,
        }
        if request.draft_value is not None:
            try:
                payload["draft_answer"] = {"value": request.draft_value, "submitted": False,
                                           "response": current.preview_response(request.draft_value)}
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
        try:
            turn = submit_chat_turn(
                system=(PROMPTS_DIR / "clickthrough_clarification.md").read_text(encoding="utf-8"),
                payload=payload,
            )
        except Exception as exc:
            # Never expose provider errors, credentials, or network details to the page.
            raise HTTPException(status_code=503, detail="The clarification chat could not connect. Please try again or ask clinic staff. The approved page explanation is still available.") from exc
        if turn.user_intent == "answer_node":
            reply = "Please use the answer choices on the page to record your answer. I can explain this question, but I cannot choose a checkbox or move you forward from this chat."
            intent = "ask_about_complaint"
        elif turn.user_intent == "off_topic":
            reply = f"Let’s keep this chat on the current {current.page()['section']} question. Clinic staff can help with other topics."
            intent = "off_topic"
        else:
            reply = turn.assistant_reply
            intent = "ask_about_complaint"
        return ChatTurnResponse(user_intent=intent, assistant_reply=reply, next_node_id=None, answer_confidence_pct=None)

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7861)
    parser.add_argument("--complaint-fields", type=Path, default=ROOT / "examples/complaints/original-creditor.json")
    parser.add_argument("--debug", action="store_true", help="Enable section jumps and example intake defaults; disable research collection.")
    parser.add_argument("--blank", action="store_true", help="Start without prefilled example fields.")
    parser.add_argument("--collection-dir", type=Path, default=ROOT / "output/clickthrough",
                        help="Directory for the three CSV datasets and their durable local database.")
    args = parser.parse_args()
    try:
        values = {} if args.blank else json.loads(args.complaint_fields.read_text(encoding="utf-8"))
        if not isinstance(values, dict):
            raise ValueError("Complaint fields must be a JSON object.")
        app = create_app(values, collection_dir=args.collection_dir, debug=args.debug)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    import uvicorn
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
