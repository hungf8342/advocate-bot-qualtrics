#!/usr/bin/env python3
"""Run the guided defense prototype: .venv/bin/python scripts/guided_clickthrough_demo.py."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from advocate_bot_qualtrics.config import PROMPTS_DIR
from advocate_bot_qualtrics.core.schemas import ChatTurnResponse
from advocate_bot_qualtrics.llm.chat_structured import submit_chat_turn
from advocate_bot_qualtrics.practice_areas.consumer_debt.guided_sol import (
    GuidedAdvanceRequest, GuidedEditRequest, GuidedRequest, GuidedSolReview,
    advance_review, edit_review,
)

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "scripts/assets/guided_sol"


class HelpMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=5000)


class HelpRequest(GuidedRequest):
    question: str = Field(min_length=1, max_length=1500)
    conversation: list[HelpMessage] = Field(default_factory=list, max_length=12)


def create_app(complaint_fields: dict | None = None) -> FastAPI:
    defaults = dict(complaint_fields or {})
    GuidedSolReview(defaults)  # Fail early on an invalid example input.
    app = FastAPI(title="Debt case guide · Guided defense prototype", docs_url=None, redoc_url=None)
    app.mount("/assets", StaticFiles(directory=ASSETS), name="assets")

    def review(request: GuidedRequest) -> GuidedSolReview:
        try:
            if request.revision:
                GuidedSolReview(defaults).replay(request.revision.previous_history)
            current = GuidedSolReview(defaults).replay(request.history)
            current.revision = request.revision
            return current
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/")
    def index():
        return FileResponse(ASSETS / "index.html", headers={"Cache-Control": "no-store"})

    @app.post("/api/state")
    def state(request: GuidedRequest):
        return review(request).page()

    def workflow_result(current: GuidedSolReview):
        return {"history": [a.model_dump(mode="json") for a in current.history],
                "revision": current.revision.model_dump(mode="json") if current.revision else None,
                "page": current.page()}

    @app.post("/api/edit")
    def edit(request: GuidedEditRequest):
        review(request)
        try:
            return workflow_result(edit_review(defaults, request))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/advance")
    def advance(request: GuidedAdvanceRequest):
        review(request)
        try:
            return workflow_result(advance_review(defaults, request))
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
        try:
            turn = submit_chat_turn(
                system=(PROMPTS_DIR / "guided_sol_clarification_system.md").read_text(encoding="utf-8"),
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
    parser.add_argument("--blank", action="store_true", help="Start without prefilled example fields.")
    args = parser.parse_args()
    try:
        values = {} if args.blank else json.loads(args.complaint_fields.read_text(encoding="utf-8"))
        if not isinstance(values, dict):
            raise ValueError("Complaint fields must be a JSON object.")
        app = create_app(values)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    import uvicorn
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
