"""Reusable host engine for the interactive decision tree."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date

from advocate_bot_qualtrics.config import (
    get_confidence_hedge_threshold,
    get_session_fields_xlsx_path,
    load_chat_system_prompt,
)
from advocate_bot_qualtrics.decision_tree.confidence import is_pure_idk, resolve_confidence_hedge_message
from advocate_bot_qualtrics.decision_tree.errors import ChatError
from advocate_bot_qualtrics.decision_tree.interactive_computations import (
    run_fdcpa_computation,
    run_sol_computation,
)
from advocate_bot_qualtrics.decision_tree.interactive_session import (
    InteractiveSessionState,
    advance_from_hook,
    apply_interactive_branch,
    init_session_from_fact_sheet,
    is_interactive_hook_node,
    record_node_answer,
)
from advocate_bot_qualtrics.decision_tree.interactive_tree import (
    INTERACTIVE_ROUTES,
    INTERACTIVE_START_NODE_ID,
    INTERACTIVE_TREE,
    idk_skip_branch_for_node,
    resolve_interactive_next_node,
)
from advocate_bot_qualtrics.decision_tree.party_labels import annotate_party_terms
from advocate_bot_qualtrics.decision_tree.process_chat import process_chat
from advocate_bot_qualtrics.decision_tree.schemas import ChatTurnResponse, CurrentNode
from advocate_bot_qualtrics.decision_tree.session_field_export import append_session_fields_row
from advocate_bot_qualtrics.llm.chat_structured import submit_chat_turn
from advocate_bot_qualtrics.schemas.complaint_fact_sheet import ComplaintFactSheet

MAX_TRANSCRIPT_TURNS = 8
REVIEW_QUESTIONS_NODE_ID = "review_questions"
_DIFFERENT_COMPLAINT_RESTART_NODES = frozenset(
    {"different_complaint_filing", "different_complaint_last_payment"}
)
_RESTART_FILING_CONFIRM_MESSAGE = (
    "Let's confirm the filing date again for this complaint."
)

_FILING_TOKEN = "{date_complaint_filed}"
_LAST_PAYMENT_TOKEN = "{date_user_failed_to_pay}"

_DATE_PARSE_CLARIFICATION = (
    "I couldn't read a date from that message. Please reply with a date only, "
    "such as 2024-01-04 or 01/04/2024 (month name formats like January 4, 2024 also work)."
)
_IDK_SKIP_MESSAGE = "No problem — we'll move on."

logger = logging.getLogger(__name__)

# Only optional additional-payment date nodes may be skipped when already captured.
# Dispute correction nodes (get_filing_date, get_last_payment_complaint) are seeded
# from the fact sheet and must still be shown when the user disputes those dates.
_DATE_NODE_FIELDS: dict[str, str] = {
    "get_last_payment_OG_creditor": "last_payment_og_creditor",
    "get_last_payment_debt_collector": "last_payment_debt_collector",
}
_DISPUTE_DATE_NODES = frozenset({"get_filing_date", "get_last_payment_complaint"})

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


@dataclass
class InteractiveChatStep:
    assistant_messages: list[str]
    current_node_id: str
    tree_complete: bool
    user_intent: str | None = None
    branch_id: str | None = None
    confidence_pct: int | None = None
    error: str | None = None


@dataclass
class InteractiveChatEngine:
    facts: ComplaintFactSheet
    session: InteractiveSessionState
    current_node_id: str = INTERACTIVE_START_NODE_ID
    transcript: list[tuple[str, str]] = field(default_factory=list)
    tree_complete: bool = False
    export_done: bool = False
    last_export_path: str | None = None
    last_outcomes: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_fact_sheet(cls, facts: ComplaintFactSheet) -> InteractiveChatEngine:
        engine = cls(
            facts=facts,
            session=init_session_from_fact_sheet(facts),
        )
        engine._drain_hooks()
        return engine

    def reset(self) -> list[str]:
        self.session = init_session_from_fact_sheet(self.facts)
        self.current_node_id = INTERACTIVE_START_NODE_ID
        self.transcript = []
        self.tree_complete = False
        self.export_done = False
        self.last_export_path = None
        self.last_outcomes = {}
        self._drain_hooks()
        return self.initial_messages()

    def initial_messages(self) -> list[str]:
        if self.transcript:
            return [text for role, text in self.transcript if role == "assistant"]
        message = self._append_transcript(
            "assistant", self._format_node_prompt(self.current_node_id)
        )
        return [message]

    def debug_snapshot(self, *, facts_path: str | None = None) -> dict:
        status = (
            "Tree complete — ask anything"
            if self.tree_complete
            else "In progress"
        )
        return {
            "facts_path": facts_path or "",
            "current_node_id": self.current_node_id,
            "tree_status": status,
            "filing_date": _fmt_date(self.session.filing_date),
            "last_payment_complaint": _fmt_date(self.session.last_payment_complaint),
            "last_payment_og_creditor": _fmt_date(self.session.last_payment_og_creditor),
            "last_payment_debt_collector": _fmt_date(self.session.last_payment_debt_collector),
            "filing_date_changed": self.session.filing_date_changed,
            "last_payment_date_changed": self.session.last_payment_date_changed,
            "threatened": self.session.threatened,
            "disclosed": self.session.disclosed,
            "evidence": self.session.evidence,
            "sol_outcome": self.last_outcomes.get("sol", "—"),
            "fdcpa_outcome": self.last_outcomes.get("fdcpa", "—"),
            "node_answers": {
                node_id: {
                    "branch": record.branch_id,
                    "confidence_pct": record.confidence_pct,
                    "skipped": record.skipped,
                }
                for node_id, record in self.session.node_answers.items()
            },
            "session_fields_xlsx": self.last_export_path or "",
        }

    def _set_tree_complete(self) -> None:
        if self.tree_complete:
            return
        self.tree_complete = True
        self._maybe_export_session_fields()

    def _maybe_export_session_fields(self) -> None:
        if self.export_done:
            return
        try:
            path = append_session_fields_row(
                get_session_fields_xlsx_path(),
                self.session,
            )
            self.last_export_path = str(path)
            self.export_done = True
        except Exception:
            logger.exception("Failed to append session fields to Excel")

    def submit(self, user_message: str) -> InteractiveChatStep:
        user_message = user_message.strip()
        if not user_message:
            return InteractiveChatStep(
                assistant_messages=[],
                current_node_id=self.current_node_id,
                tree_complete=self.tree_complete,
                error="Please enter a message.",
            )

        self._append_transcript("user", user_message)

        if is_interactive_hook_node(self.current_node_id):
            messages = self._drain_hooks()
            return InteractiveChatStep(
                assistant_messages=messages,
                current_node_id=self.current_node_id,
                tree_complete=self.tree_complete,
            )

        if self.current_node_id == REVIEW_QUESTIONS_NODE_ID:
            return self._submit_terminal_qa(user_message)

        return self._submit_tree_node(user_message)

    def _submit_tree_node(self, user_message: str) -> InteractiveChatStep:
        node_id = self.current_node_id
        rendered = render_interactive_node(node_id, self.facts, self.session)

        skip_branch = idk_skip_branch_for_node(node_id)
        if skip_branch is not None and is_pure_idk(user_message):
            return self._advance_on_branch(
                node_id=node_id,
                branch_id=skip_branch,
                user_message=user_message,
                confidence_pct=0,
                skipped=True,
                prefix_messages=[_IDK_SKIP_MESSAGE],
            )

        payload = build_user_payload(self.transcript, user_message)

        try:
            turn = process_chat(payload, rendered, self.facts)
        except ChatError as exc:
            return InteractiveChatStep(
                assistant_messages=[],
                current_node_id=self.current_node_id,
                tree_complete=self.tree_complete,
                error=f"Chat routing error: {exc}",
            )
        except Exception as exc:
            return InteractiveChatStep(
                assistant_messages=[],
                current_node_id=self.current_node_id,
                tree_complete=self.tree_complete,
                error=f"API error: {exc}. Check ANTHROPIC_API_KEY and retry.",
            )

        if turn.user_intent == "answer_node" and turn.next_node_id:
            parsed_from_message = parse_submitted_date(user_message)

            if turn.next_node_id == "submit" and parsed_from_message is None:
                clarification = self._append_transcript(
                    "assistant", _DATE_PARSE_CLARIFICATION
                )
                return InteractiveChatStep(
                    assistant_messages=[clarification],
                    current_node_id=self.current_node_id,
                    tree_complete=self.tree_complete,
                    user_intent=turn.user_intent,
                    branch_id=turn.next_node_id,
                    confidence_pct=turn.answer_confidence_pct,
                )

            confidence_pct = turn.answer_confidence_pct or 0
            step = self._advance_on_branch(
                node_id=node_id,
                branch_id=turn.next_node_id,
                user_message=user_message,
                confidence_pct=confidence_pct,
                parsed_from_message=parsed_from_message,
                prefix_messages=self._hedge_prefix_messages(
                    turn.assistant_reply, confidence_pct
                ),
            )
            step.user_intent = turn.user_intent
            return step

        messages = [self._append_transcript("assistant", turn.assistant_reply)]

        if turn.user_intent == "ask_about_complaint":
            reask = self._format_node_prompt(self.current_node_id)
            messages.append(self._append_transcript("assistant", reask))

        return InteractiveChatStep(
            assistant_messages=messages,
            current_node_id=self.current_node_id,
            tree_complete=self.tree_complete,
            user_intent=turn.user_intent,
            branch_id=turn.next_node_id,
        )

    def _hedge_prefix_messages(
        self,
        assistant_reply: str,
        confidence_pct: int,
    ) -> list[str]:
        if confidence_pct >= get_confidence_hedge_threshold():
            return []
        message = resolve_confidence_hedge_message(assistant_reply)
        return [message]

    def _advance_on_branch(
        self,
        *,
        node_id: str,
        branch_id: str,
        user_message: str,
        confidence_pct: int,
        skipped: bool = False,
        parsed_from_message: date | None = None,
        prefix_messages: list[str] | None = None,
    ) -> InteractiveChatStep:
        submitted_date = (
            parsed_from_message if branch_id in {"submit", "yes"} else None
        )
        apply_interactive_branch(
            self.session,
            node_id,
            branch_id,
            submitted_date=submitted_date,
        )
        record_node_answer(
            self.session,
            node_id,
            branch_id,
            confidence_pct,
            skipped=skipped,
        )

        next_id = resolve_interactive_next_node(node_id, branch_id, self.session)
        messages: list[str] = []
        for text in prefix_messages or []:
            messages.append(self._append_transcript("assistant", text))

        if next_id:
            next_id = _skip_date_node_if_collected(next_id, self.session)
            self.current_node_id = next_id
            embedded = parsed_from_message if not skipped else None
            self._consume_embedded_dispute_date(embedded)
            if self.current_node_id == REVIEW_QUESTIONS_NODE_ID:
                self._set_tree_complete()
            messages.extend(self._drain_hooks())
            if (
                node_id in _DIFFERENT_COMPLAINT_RESTART_NODES
                and branch_id == "yes"
                and self.current_node_id == INTERACTIVE_START_NODE_ID
            ):
                messages.append(
                    self._append_transcript("assistant", _RESTART_FILING_CONFIRM_MESSAGE)
                )
            if not is_interactive_hook_node(self.current_node_id):
                prompt = self._append_next_question()
                if prompt:
                    messages.append(prompt)

        return InteractiveChatStep(
            assistant_messages=messages,
            current_node_id=self.current_node_id,
            tree_complete=self.tree_complete,
            user_intent="answer_node",
            branch_id=branch_id,
            confidence_pct=confidence_pct,
        )

    def _submit_terminal_qa(self, user_message: str) -> InteractiveChatStep:
        self._set_tree_complete()
        rendered = render_interactive_node(
            REVIEW_QUESTIONS_NODE_ID, self.facts, self.session
        )
        payload = build_user_payload(self.transcript, user_message)

        try:
            turn = _process_terminal_qa(payload, rendered, self.facts)
        except ChatError as exc:
            return InteractiveChatStep(
                assistant_messages=[],
                current_node_id=self.current_node_id,
                tree_complete=True,
                error=f"Chat error: {exc}",
            )
        except Exception as exc:
            return InteractiveChatStep(
                assistant_messages=[],
                current_node_id=self.current_node_id,
                tree_complete=True,
                error=f"API error: {exc}. Check ANTHROPIC_API_KEY and retry.",
            )

        reply = self._append_transcript("assistant", turn.assistant_reply)
        return InteractiveChatStep(
            assistant_messages=[reply],
            current_node_id=self.current_node_id,
            tree_complete=True,
            user_intent=turn.user_intent,
        )

    def _drain_hooks(self) -> list[str]:
        messages: list[str] = []
        while is_interactive_hook_node(self.current_node_id):
            if self.current_node_id == "sol_computation":
                outcome = run_sol_computation(self.session)
                self.last_outcomes["sol"] = outcome
            else:
                outcome = run_fdcpa_computation(self.session)
                self.last_outcomes["fdcpa"] = outcome

            rendered = render_interactive_node(
                self.current_node_id, self.facts, self.session
            )
            text = f"{rendered.question}\n\nResult: {outcome}"
            messages.append(self._append_transcript("assistant", text))

            next_id = advance_from_hook(self.current_node_id)
            if not next_id:
                break
            self.current_node_id = next_id
            if self.current_node_id == REVIEW_QUESTIONS_NODE_ID:
                self._set_tree_complete()

        return messages

    def _consume_embedded_dispute_date(self, embedded_date: date | None) -> None:
        """Apply a date from the user's message and skip the dispute correction node."""
        if embedded_date is None or self.current_node_id not in _DISPUTE_DATE_NODES:
            return
        apply_interactive_branch(
            self.session,
            self.current_node_id,
            "submit",
            submitted_date=embedded_date,
        )
        next_id = resolve_interactive_next_node(
            self.current_node_id, "submit", self.session
        )
        if not next_id:
            return
        self.current_node_id = _skip_date_node_if_collected(next_id, self.session)
        if self.current_node_id == REVIEW_QUESTIONS_NODE_ID:
            self._set_tree_complete()

    def _append_next_question(self) -> str | None:
        message = self._format_node_prompt(self.current_node_id)
        return self._append_transcript("assistant", message)

    def _format_node_prompt(self, node_id: str) -> str:
        node = render_interactive_node(node_id, self.facts, self.session)
        return node.question

    def _append_transcript(self, role: str, text: str) -> str:
        if role == "assistant":
            text = annotate_party_terms(text, self.facts)
        self.transcript.append((role, text))
        return text


def render_interactive_node(
    node_id: str,
    facts: ComplaintFactSheet,
    session: InteractiveSessionState,
) -> CurrentNode:
    source = INTERACTIVE_TREE[node_id]
    filing = session.filing_date or facts.date_complaint_filed
    last_payment = session.last_payment_complaint or facts.date_user_failed_to_pay

    question = source.question.replace(_FILING_TOKEN, _fmt_date(filing))
    question = question.replace(_LAST_PAYMENT_TOKEN, _fmt_date(last_payment))
    question = annotate_party_terms(question, facts)

    branches = [
        branch.model_copy(
            update={
                "label": annotate_party_terms(
                    branch.label.replace(_FILING_TOKEN, _fmt_date(filing)).replace(
                        _LAST_PAYMENT_TOKEN, _fmt_date(last_payment)
                    ),
                    facts,
                )
            }
        )
        for branch in source.branches
    ]
    return source.model_copy(update={"question": question, "branches": branches})


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


def _skip_date_node_if_collected(
    next_node_id: str, session: InteractiveSessionState
) -> str:
    """Skip a date-collection node when that date was already captured."""
    field = _DATE_NODE_FIELDS.get(next_node_id)
    if field is None or getattr(session, field) is None:
        return next_node_id
    skip_to = INTERACTIVE_ROUTES.get((next_node_id, "submit"))
    return skip_to if skip_to else next_node_id


def build_user_payload(
    transcript: list[tuple[str, str]],
    latest_user_message: str,
    *,
    max_turns: int = MAX_TRANSCRIPT_TURNS,
) -> str:
    max_messages = max_turns * 2
    recent = transcript[-max_messages:] if transcript else []

    lines = ["Recent transcript:"]
    if recent:
        for role, text in recent:
            prefix = "User" if role == "user" else "Assistant"
            lines.append(f"{prefix}: {text}")
    else:
        lines.append("(none)")

    lines.append("")
    lines.append(f"Latest user message:\nUser: {latest_user_message}")
    return "\n".join(lines)


def _process_terminal_qa(
    user_message: str,
    current_node: CurrentNode,
    fact_sheet: ComplaintFactSheet,
) -> ChatTurnResponse:
    system_prompt = load_chat_system_prompt()
    qa_hint = (
        "The user is in the final open Q&A phase after completing the decision tree. "
        "Answer using ask_about_complaint, unclear, or off_topic intent only. "
        "Do not use answer_node."
    )
    payload = {
        "current_node": current_node.model_dump(),
        "complaint_fact_sheet": fact_sheet.model_dump(
            mode="json", exclude={"field_citations"}
        ),
        "user_message": user_message,
        "phase_hint": qa_hint,
    }
    turn = submit_chat_turn(system=system_prompt, payload=payload)
    if turn.user_intent == "answer_node":
        raise ChatError("Terminal Q&A must not use answer_node intent.")
    if turn.next_node_id is not None:
        return ChatTurnResponse.model_validate(
            {**turn.model_dump(), "next_node_id": None}
        )
    return turn


def _fmt_date(value: date | None) -> str:
    return value.isoformat() if value else "unknown"
