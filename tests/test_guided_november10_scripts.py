"""November 10 summary descriptors, source changes, and ordered mitigation edits."""
import pytest

from advocate_bot_qualtrics.practice_areas.consumer_debt.workflow import (
    CONTENT, DEFENSES, GuidedEditRequest, edit_review,
)
from advocate_bot_qualtrics.practice_areas.consumer_debt.script_formatting import SOURCE_FORMATTING
from test_guided_november9_screens import begin, start, step


@pytest.mark.parametrize('defense', DEFENSES)
def test_summary_rows_use_source_descriptors_without_ordinal_labels(defense):
    current = start(defense)
    rows = current._rows(defense)
    assert rows[0]['label'] == DEFENSES[defense]['label']
    source = '\n'.join(p['text'] for p in SOURCE_FORMATTING['paragraphs']).casefold()
    expected = CONTENT['summary_labels'].get(defense, {})
    for row in rows[1:]:
        assert row['label'] == expected[row['id']]
        assert row['label'].casefold() in source
        assert row['detail'] == 'Nested checkbox'
        assert row['status'] == 'Not offered on this path'


@pytest.mark.parametrize('consolidation', ['yes', 'no'])
def test_uncertain_settlement_returns_to_first_question_before_any_contact(consolidation):
    current = begin('failure_to_mitigate', consolidation=consolidation)
    current = step(current, 'unknown')
    assert current.page()['title'] == 'Ready to return to the pending question?'
    assert 'declining a settlement offer' in ' '.join(current.page()['body'])
    current = step(current)
    assert current.current == 'mitigation_settlement_resolve'
    title = current.page()['title']
    assert ('debt consolidation company' in title) == (consolidation == 'yes')
    current = step(current, 'yes')
    assert current.current == 'mitigation_first_checkbox'
    assert not any(a.node_id.startswith('mitigation_contact') for a in current.history)
    current = step(current, 'yes')
    assert current.current == 'mitigation_contact'


@pytest.mark.parametrize('consolidation', ['yes', 'no'])
def test_mitigation_edit_reconciles_both_nested_choices_in_the_new_order(consolidation):
    current = begin('failure_to_mitigate', consolidation=consolidation)
    for value in ['yes', 'yes', 'no', 'yes', 'continue']:
        current = step(current, value)
    assert current.current == DEFENSES['failure_to_mitigate']['summary']
    rows = current.page()['rows']
    assert [r['label'] for r in rows[1:]] == [
        'Settlement offer declined before suit', 'Attempted collection or settlement before suit']
    assert all(r['checked'] for r in rows)
    index = next(i for i, a in enumerate(current.history) if a.node_id == 'mitigation_settlement')
    current = edit_review(current.defaults, GuidedEditRequest(
        history=current.history, debug_section=current.debug_section, edit_index=index, value='no'))
    for _ in range(10):
        if current.current == DEFENSES['failure_to_mitigate']['summary']:
            break
        assert current.page()['input_type'] == 'continue'
        current = step(current)
    assert current.current == DEFENSES['failure_to_mitigate']['summary']
    choices = current.session.checkbox_selections['failure_to_mitigate']
    assert choices.get('first') != 'include'
    assert choices['second'] == choices['main'] == 'include'
    assert not any(a.node_id == 'mitigation_first_checkbox' for a in current.history)
