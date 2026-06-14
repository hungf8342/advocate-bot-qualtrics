"""Reusable host engine for the interactive decision tree."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from advocate_bot_qualtrics.config import load_chat_system_prompt
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
)
from advocate_bot_qualtrics.decision_tree.interactive_tree import (
    INTERACTIVE_ROUTES,
    INTERACTIVE_START_NODE_ID,
    INTERACTIVE_TREE,
    resolve_interactive_next_node,
)
from advocate_bot_qualtrics.decision_tree.process_chat import process_chat
from advocate_bot_qualtrics.decision_tree.schemas import ChatTurnResponse, CurrentNode
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
    error: str | None = None


@dataclass
class InteractiveChatEngine:
    facts: ComplaintFactSheet
    session: InteractiveSessionState
    current_node_id: str = INTERACTIVE_START_NODE_ID
    transcript: list[tuple[str, str]] = field(default_factory=list)
    tree_complete: bool = False
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
        self.last_outcomes = {}
        self._drain_hooks()
        return self.initial_messages()

    def initial_messages(self) -> list[str]:
        if self.transcript:
            return [text for role, text in self.transcript if role == "assistant"]
        message = self._format_node_prompt(self.current_node_id)
        self._append_transcript("assistant", message)
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
        }

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
                self._append_transcript("assistant", _DATE_PARSE_CLARIFICATION)
                return InteractiveChatStep(
                    assistant_messages=[_DATE_PARSE_CLARIFICATION],
                    current_node_id=self.current_node_id,
                    tree_complete=self.tree_complete,
                    user_intent=turn.user_intent,
                    branch_id=turn.next_node_id,
                )

            submitted_date = (
                parsed_from_message
                if turn.next_node_id in {"submit", "yes"}
                else None
            )
            apply_interactive_branch(
                self.session,
                node_id,
                turn.next_node_id,
                submitted_date=submitted_date,
            )
            next_id = resolve_interactive_next_node(
                node_id, turn.next_node_id, self.session
            )
            messages: list[str] = []
            if next_id:
                next_id = _skip_date_node_if_collected(next_id, self.session)
                self.current_node_id = next_id
                self._consume_embedded_dispute_date(parsed_from_message)
                if self.current_node_id == REVIEW_QUESTIONS_NODE_ID:
                    self.tree_complete = True
                messages.extend(self._drain_hooks())
                if (
                    node_id in _DIFFERENT_COMPLAINT_RESTART_NODES
                    and turn.next_node_id == "yes"
                    and self.current_node_id == INTERACTIVE_START_NODE_ID
                ):
                    messages.append(_RESTART_FILING_CONFIRM_MESSAGE)
                    self._append_transcript("assistant", _RESTART_FILING_CONFIRM_MESSAGE)
                if not is_interactive_hook_node(self.current_node_id):
                    prompt = self._append_next_question()
                    if prompt:
                        messages.append(prompt)
        else:
            messages = [turn.assistant_reply]
            self._append_transcript("assistant", turn.assistant_reply)

        return InteractiveChatStep(
            assistant_messages=messages,
            current_node_id=self.current_node_id,
            tree_complete=self.tree_complete,
            user_intent=turn.user_intent,
            branch_id=turn.next_node_id,
        )

    def _submit_terminal_qa(self, user_message: str) -> InteractiveChatStep:
        self.tree_complete = True
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

        self._append_transcript("assistant", turn.assistant_reply)
        return InteractiveChatStep(
            assistant_messages=[turn.assistant_reply],
            current_node_id=self.current_node_id,
            tree_complete=True,
            user_intent=turn.user_intent,
        )

    def _drain_hooks(self) -> list[str]:
        messages: list[str] = []
        while is_interactive_hook_node(self.current_node_id):
            node = INTERACTIVE_TREE[self.current_node_id]
            if self.current_node_id == "sol_computation":
                outcome = run_sol_computation(self.session)
                self.last_outcomes["sol"] = outcome
            else:
                outcome = run_fdcpa_computation(self.session)
                self.last_outcomes["fdcpa"] = outcome

            text = f"{node.question}\n\nResult: {outcome}"
            messages.append(text)
            self._append_transcript("assistant", text)

            next_id = advance_from_hook(self.current_node_id)
            if not next_id:
                break
            self.current_node_id = next_id
            if self.current_node_id == REVIEW_QUESTIONS_NODE_ID:
                self.tree_complete = True

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
            self.tree_complete = True

    def _append_next_question(self) -> str | None:
        message = self._format_node_prompt(self.current_node_id)
        self._append_transcript("assistant", message)
        return message

    def _format_node_prompt(self, node_id: str) -> str:
        node = render_interactive_node(node_id, self.facts, self.session)
        return node.question

    def _append_transcript(self, role: str, text: str) -> None:
        self.transcript.append((role, text))


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

    branches = [
        branch.model_copy(
            update={
                "label": branch.label.replace(_FILING_TOKEN, _fmt_date(filing)).replace(
                    _LAST_PAYMENT_TOKEN, _fmt_date(last_payment)
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
