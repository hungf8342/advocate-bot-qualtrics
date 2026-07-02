"""Subject-agnostic interactive decision-tree junction engine."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from advocate_bot_qualtrics.config import get_confidence_hedge_threshold
from advocate_bot_qualtrics.core.bundle import PracticeAreaBundle, get_bundle
from advocate_bot_qualtrics.core.confidence import is_pure_idk, resolve_confidence_hedge_message
from advocate_bot_qualtrics.core.dates import ParsedDate, parse_submitted_date, parse_user_date
from advocate_bot_qualtrics.core.errors import ChatError
from advocate_bot_qualtrics.core.schemas import ChatTurnResponse, CurrentNode
from advocate_bot_qualtrics.core.session import record_node_answer
from advocate_bot_qualtrics.llm.chat_structured import submit_chat_turn

MAX_TRANSCRIPT_TURNS = 8

_DATE_PARSE_CLARIFICATION = (
    "I couldn't read a date from that message. Please reply with a date only, "
    "such as 2024-01-04 or 01/04/2024 (month name formats like January 4, 2024 also work)."
)
_IDK_SKIP_MESSAGE = "No problem — we'll move on."

_FIRST_TURN_BARE_ABSTENTION_MAX_LEN = 40

logger = logging.getLogger(__name__)


def _is_first_user_turn(transcript: list[tuple[str, str]]) -> bool:
    return sum(1 for role, _ in transcript if role == "user") == 1


def _is_short_bare_abstention(user_message: str) -> bool:
    stripped = user_message.strip()
    if "?" in stripped:
        return False
    if len(stripped) > _FIRST_TURN_BARE_ABSTENTION_MAX_LEN:
        return False
    return is_pure_idk(stripped)


def should_apply_pure_idk_skip(
    transcript: list[tuple[str, str]], user_message: str
) -> bool:
    if not is_pure_idk(user_message):
        return False
    if _is_first_user_turn(transcript):
        return _is_short_bare_abstention(user_message)
    return True


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
    facts: Any
    session: Any
    bundle: PracticeAreaBundle | None = None
    current_node_id: str = ""
    transcript: list[tuple[str, str]] = field(default_factory=list)
    tree_complete: bool = False
    export_done: bool = False
    last_export_path: str | None = None
    last_outcomes: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.bundle is None:
            self.bundle = get_bundle("consumer_debt")
        if not self.current_node_id:
            self.current_node_id = self.bundle.start_node_id

    @classmethod
    def from_fact_sheet(
        cls,
        facts: Any,
        *,
        bundle: PracticeAreaBundle | None = None,
        practice_area_id: str = "consumer_debt",
    ) -> InteractiveChatEngine:
        area = bundle or get_bundle(practice_area_id)
        engine = cls(
            bundle=area,
            facts=facts,
            session=area.init_session(facts),
        )
        engine._drain_hooks()
        return engine

    def reset(self) -> list[str]:
        self.session = self.bundle.init_session(self.facts)
        self.current_node_id = self.bundle.start_node_id
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
        return self.bundle.build_debug_snapshot(
            session=self.session,
            current_node_id=self.current_node_id,
            tree_complete=self.tree_complete,
            last_outcomes=self.last_outcomes,
            last_export_path=self.last_export_path,
            facts_path=facts_path,
        )

    def _set_tree_complete(self) -> None:
        if self.tree_complete:
            return
        self.tree_complete = True
        self._maybe_export_session_fields()

    def _maybe_export_session_fields(self) -> None:
        if self.export_done:
            return
        try:
            from advocate_bot_qualtrics.decision_tree.interactive_host import (
                get_session_fields_xlsx_path,
            )

            path = self.bundle.append_session_fields_row(
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

        if self.bundle.is_hook_node(self.current_node_id):
            messages = self._drain_hooks()
            return InteractiveChatStep(
                assistant_messages=messages,
                current_node_id=self.current_node_id,
                tree_complete=self.tree_complete,
            )

        if self.current_node_id == self.bundle.terminal_node_id:
            return self._submit_terminal_qa(user_message)

        return self._submit_tree_node(user_message)

    def _submit_tree_node(self, user_message: str) -> InteractiveChatStep:
        node_id = self.current_node_id
        rendered = self.bundle.render_node(node_id, self.facts, self.session)
        parsed_from_message = self._parse_user_date_for_node(node_id, user_message)

        skip_branch = self.bundle.idk_skip_branch(node_id)
        if skip_branch is not None and should_apply_pure_idk_skip(
            self.transcript, user_message
        ):
            if self.bundle.is_date_submit_node(node_id) and parsed_from_message is not None:
                pass
            else:
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
            from advocate_bot_qualtrics.decision_tree.interactive_host import process_chat

            turn = process_chat(payload, rendered, self.facts, self.bundle)
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
            effective_branch_id = turn.next_node_id
            if turn.next_node_id == "no_date" and parsed_from_message is not None:
                effective_branch_id = "submit"

            if effective_branch_id == "submit" and parsed_from_message is None:
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
            confidence_pct = self.bundle.adjust_date_answer_confidence(
                self.session,
                node_id,
                parsed_from_message,
                confidence_pct,
            )
            step = self._advance_on_branch(
                node_id=node_id,
                branch_id=effective_branch_id,
                user_message=user_message,
                confidence_pct=confidence_pct,
                parsed_from_message=parsed_from_message.value if parsed_from_message else None,
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

    def _parse_user_date_for_node(
        self, node_id: str, user_message: str
    ) -> ParsedDate | None:
        if not self.bundle.is_date_submit_node(node_id):
            exact = parse_submitted_date(user_message)
            if exact is None:
                return None
            return ParsedDate(value=exact, approximate=False, source="exact")

        return parse_user_date(
            user_message,
            anchor_date=getattr(self.session, "filing_date", None),
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
        self.bundle.apply_branch(
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

        next_id = self.bundle.resolve_next_node(node_id, branch_id, self.session)
        messages: list[str] = []
        for text in prefix_messages or []:
            messages.append(self._append_transcript("assistant", text))

        if next_id:
            next_id = self.bundle.skip_collected_date_node(next_id, self.session)
            self.current_node_id = next_id
            embedded = parsed_from_message if not skipped else None
            self.bundle.consume_embedded_dispute_date(
                self, embedded, terminal_node_id=self.bundle.terminal_node_id
            )
            if self.current_node_id == self.bundle.terminal_node_id:
                self._set_tree_complete()
            messages.extend(self._drain_hooks())
            if (
                node_id in self.bundle.different_complaint_restart_nodes
                and branch_id == "yes"
                and self.current_node_id == self.bundle.start_node_id
            ):
                messages.append(
                    self._append_transcript(
                        "assistant", self.bundle.restart_filing_confirm_message
                    )
                )
            if not self.bundle.is_hook_node(self.current_node_id):
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
        rendered = self.bundle.render_node(
            self.bundle.terminal_node_id, self.facts, self.session
        )
        payload = build_user_payload(self.transcript, user_message)

        try:
            from advocate_bot_qualtrics.decision_tree.interactive_host import _process_terminal_qa

            turn = _process_terminal_qa(payload, rendered, self.facts, self.bundle)
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
        while self.bundle.is_hook_node(self.current_node_id):
            outcome = self.bundle.run_hook(self.session, self.current_node_id)
            outcome_key = self.bundle.hook_outcome_key(self.current_node_id)
            if outcome_key:
                self.last_outcomes[outcome_key] = outcome

            rendered = self.bundle.render_node(
                self.current_node_id, self.facts, self.session
            )
            text = f"{rendered.question}\n\nResult: {outcome}"
            messages.append(self._append_transcript("assistant", text))

            next_id = self.bundle.advance_from_hook(self.current_node_id)
            if not next_id:
                break
            self.current_node_id = next_id
            if self.current_node_id == self.bundle.terminal_node_id:
                self._set_tree_complete()

        return messages

    def _append_next_question(self) -> str | None:
        message = self._format_node_prompt(self.current_node_id)
        return self._append_transcript("assistant", message)

    def _format_node_prompt(self, node_id: str) -> str:
        node = self.bundle.render_node(node_id, self.facts, self.session)
        return node.question

    def _append_transcript(self, role: str, text: str) -> str:
        if role == "assistant":
            text = self.bundle.annotate_assistant_text(text, self.facts)
        self.transcript.append((role, text))
        return text


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
    facts: Any,
    bundle: PracticeAreaBundle,
) -> ChatTurnResponse:
    system_prompt = bundle.load_chat_system_prompt()
    qa_hint = (
        "The user is in the final open Q&A phase after completing the decision tree. "
        "Answer using ask_about_complaint, unclear, or off_topic intent only. "
        "Do not use answer_node."
    )
    payload = {
        "current_node": current_node.model_dump(),
        bundle.facts_payload_key: bundle.facts_for_llm(facts),
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


def render_interactive_node(
    node_id: str,
    facts: Any,
    session: Any,
    *,
    practice_area_id: str = "consumer_debt",
) -> CurrentNode:
    """Compatibility helper for tests and external callers."""
    return get_bundle(practice_area_id).render_node(node_id, facts, session)


def parse_submitted_date_compat(text: str) -> date | None:
    return parse_submitted_date(text)
