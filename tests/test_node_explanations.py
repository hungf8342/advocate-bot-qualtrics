"""Node-approved help and explicit plaintiff-type categories."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from advocate_bot_qualtrics.core.schemas import ExplanationImage
from advocate_bot_qualtrics.core.tree_definition import TreeDefinition
from advocate_bot_qualtrics.practice_areas.consumer_debt.base_tree import BASE_TREE_DEFINITION as TREE


def test_plaintiff_explanation_points_to_a_real_image_and_no_text_validation():
    node = TREE.node("get_plaintiff_name")
    assert node.input.type == "text"
    assert node.validation is None
    assert node.explanation is not None
    assert "almost always in the top half of the page" in node.explanation.text
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
        assert TREE.route(node.id, branch) == "prelim_original_creditor_needed"


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
