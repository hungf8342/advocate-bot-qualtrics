"""Node-approved help and explicit plaintiff-type categories."""

from pathlib import Path
import runpy

import pytest
from pydantic import ValidationError

from advocate_bot_qualtrics.core.engine import InteractiveChatEngine
from advocate_bot_qualtrics.core.process_chat import _post_validate_turn
from advocate_bot_qualtrics.core.schemas import ChatTurnResponse, ExplanationImage
from advocate_bot_qualtrics.core.tree_definition import TreeDefinition
from advocate_bot_qualtrics.practice_areas.consumer_debt.tree import INTERACTIVE_TREE_DEFINITION as TREE


def test_plaintiff_explanation_points_to_a_real_image_and_no_text_validation():
    node = TREE.node("get_plaintiff_name")
    assert node.input.type == "text"
    assert node.validation is None
    assert node.explanation is not None
    assert "underneath the centered and bolded court name" in node.explanation.text
    assert [image.path for image in node.explanation.images] == ["complaint-examples/plaintiff.png"]
    project = Path(__file__).resolve().parents[1]
    assert (project / node.explanation.images[0].path).is_file()


def test_plaintiff_type_enum_covers_all_and_only_three_branches():
    node = TREE.node("prelim_creditor_type")
    assert node.validation.type == "enum"
    assert set(node.validation.categories) == {"original", "buyer", "unknown"}
    assert set(node.validation.categories) == {branch.id for branch in node.branches}
    assert "company name" in node.validation.categories["unknown"]
    assert "original creditor" in node.explanation.text
    assert "Midland Credit Management" in node.explanation.text
    rendered = node.to_current_node()
    assert rendered.validation == node.validation
    assert rendered.explanation == node.explanation
    for branch in ("original", "buyer", "unknown"):
        assert TREE.route(node.id, branch) == "prelim_recognize"
        accepted = _post_validate_turn(
            ChatTurnResponse(user_intent="answer_node", assistant_reply="Got it.", next_node_id=branch, answer_confidence_pct=90),
            current_node=rendered, latest_user_message=branch,
        )
        assert accepted.next_node_id == branch


def test_enum_rejects_a_missing_category():
    with pytest.raises(ValidationError, match="enum categories must describe every branch"):
        TreeDefinition.model_validate({
            "id": "invalid", "version": "1", "start_node_id": "start",
            "nodes": [{
                "id": "start", "kind": "choice", "question": "Type?",
                "validation": {"type": "enum", "categories": {"buyer": "Purchaser"}},
                "branches": [
                    {"id": "buyer", "label": "Buyer", "target": "end"},
                    {"id": "unknown", "label": "Not sure", "target": "end"},
                ],
            }, {"id": "end", "kind": "terminal", "question": "Done."}],
        })


@pytest.mark.parametrize("path", ["../secret.png", "/tmp/example.png", "https://example.com/example.png", "notes.txt"])
def test_explanation_image_requires_project_relative_image_path(path):
    with pytest.raises(ValidationError, match="relative image path"):
        ExplanationImage(path=path, alt="Example")


@pytest.mark.parametrize("node_id,phrase,image_expected", [
    ("get_plaintiff_name", "The plaintiff is who is suing you for money.", True),
    ("prelim_creditor_type", 'An "original creditor" is the company', False),
])
def test_help_uses_approved_node_text_and_stays_on_the_question(monkeypatch, node_id, phrase, image_expected):
    from advocate_bot_qualtrics.decision_tree import interactive_host

    def fake_chat(*args, **kwargs):
        return ChatTurnResponse(user_intent="ask_about_complaint", assistant_reply="Unapproved reply.")

    monkeypatch.setattr(interactive_host, "process_chat", fake_chat)
    engine = InteractiveChatEngine.from_user_input()
    engine.current_node_id = node_id
    step = engine.submit("What does that mean?")
    assert step.error is None
    assert step.user_intent == "ask_about_complaint"
    assert step.current_node_id == node_id
    assert phrase in step.assistant_messages[0]
    assert "Unapproved reply" not in step.assistant_messages[0]
    assert ("![Example complaint" in step.assistant_messages[0]) == image_expected
    assert step.assistant_messages[-1] == TREE.node(node_id).question


def test_demo_maps_approved_image_reference_to_served_project_file():
    project = Path(__file__).resolve().parents[1]
    demo = runpy.run_path(str(project / "scripts/interactive_chat_demo.py"))
    engine = InteractiveChatEngine.from_user_input()
    engine.transcript.append(("assistant", "![Example complaint](complaint-examples/plaintiff.png)"))
    content = demo["_chat_history"](engine)[-1]["content"]
    assert "/gradio_api/file=" in content
    assert "/complaint-examples/plaintiff.png" in content
