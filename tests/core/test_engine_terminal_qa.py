"""Final Q&A and bundle exports work through the canonical engine."""

from dataclasses import replace

import pytest

from advocate_bot_qualtrics.core import engine as engine_module
from advocate_bot_qualtrics.core.bundle import get_bundle
from advocate_bot_qualtrics.core.engine import InteractiveChatEngine
from advocate_bot_qualtrics.core.schemas import ChatTurnResponse


@pytest.mark.parametrize("intent,branch", [
    ("ask_about_complaint", None),
    ("ask_about_complaint", "yes"),
    ("answer_node", "yes"),
])
def test_terminal_qa_stays_complete_and_uses_bundle_export(monkeypatch, tmp_path, intent, branch):
    path = tmp_path / "custom-export.xlsx"
    bundle = replace(get_bundle("consumer_debt"), get_session_fields_xlsx_path=lambda: path)
    engine = InteractiveChatEngine.from_user_input(bundle=bundle)
    engine.current_node_id = bundle.terminal_node_id
    calls = []

    def fake_submit(*, system, payload):
        calls.append(payload)
        return ChatTurnResponse(
            user_intent=intent,
            assistant_reply="Review your checklist with clinic staff.",
            next_node_id=branch,
            answer_confidence_pct=100 if intent == "answer_node" else None,
        )

    monkeypatch.setattr(engine_module, "submit_chat_turn", fake_submit)
    step = engine.submit("What should I do next?")

    assert step.tree_complete
    assert step.current_node_id == bundle.terminal_node_id
    assert step.branch_id is None
    assert engine.export_done
    assert engine.last_export_path == str(path)
    assert path.is_file()
    assert calls[0]["current_node"]["node_id"] == bundle.terminal_node_id
    assert "Do not use answer_node" in calls[0]["phase_hint"]
    if intent == "answer_node":
        assert "Terminal Q&A must not use answer_node" in step.error
        assert step.assistant_messages == []
    else:
        assert step.error is None
        assert step.assistant_messages == ["Review your checklist with clinic staff."]
