"""Shared storage bindings keep explicit checkbox choices independent."""

import pytest

from advocate_bot_qualtrics.practice_areas.consumer_debt.session import apply_interactive_branch
from advocate_bot_qualtrics.practice_areas.consumer_debt.base_tree import BASE_TREE_DEFINITION as TREE

BOX_NODES = [n for n in TREE.nodes if n.selection_checkboxes]


@pytest.mark.parametrize('definition', BOX_NODES, ids=lambda n:n.id)
@pytest.mark.parametrize('branch,selection',[('yes','include'),('no','exclude')])
def test_each_decision_records_only_its_explicit_checkbox_choices(definition,branch,selection,verified_session):
    session=verified_session()
    # Apply through the metadata binding used by the clickthrough, without
    # traversing unrelated downstream questions for this exhaustive storage check.
    apply_interactive_branch(session,definition.id,branch)
    boxes = definition.selection_checkboxes
    assert session.checkbox_selections == {boxes[0].defense_id:{box.checkbox_id:selection for box in boxes}}
    assert session.defense_selections == {box.defense_id:selection for box in boxes if box.checkbox_id=='main'}
