"""SOL regression checks: footnote screens, cutoff routing, and shared clarification."""
from copy import deepcopy
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile
import runpy

import pytest
from fastapi.testclient import TestClient

from advocate_bot_qualtrics.practice_areas.consumer_debt.guided_sol import (
    CONTENT, DEFENSE, SUMMARY, GuidedSolReview,
)
from test_guided_sol import intake, review, advance_updated, answers, change

ROOT = Path(__file__).resolve().parents[1]


def test_source_footnotes_supply_the_sol_screen_headings():
    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    with ZipFile(ROOT / CONTENT['sol_source']) as document:
        footnotes = ET.fromstring(document.read('word/footnotes.xml'))
    headings = [''.join(t.text or '' for t in p.findall('.//w:t', ns)).strip()
                for p in footnotes.findall('w:footnote', ns)]
    current = review(intake('buyer', oral='yes'))
    for value in ['yes', 'no']:
        assert 'NEW SCREEN: ' + current.page()['title'] in headings
        current = advance_updated(current, value)
    assert 'NEW SCREEN: ' + current.page()['title'] in headings
    agreement = review(intake())
    assert 'NEW SCREEN: ' + agreement.page()['title'] in headings
    assert agreement.page()['body'][0].startswith('The complaint lists your last payment')


@pytest.mark.parametrize('filing,cutoff', [('2026-09-20', '2025-09-20'), ('2024-02-29', '2023-02-28')])
@pytest.mark.parametrize('answer,offered,ack', [
    ('yes', False, 'You said your last payment was after'),
    ('no', True, 'You said your last payment was on or before'),
    ('unknown', True, 'You’re not sure whether your last payment was after'),
])
def test_after_cutoff_answers_and_calendar_dates(filing, cutoff, answer, offered, ack):
    current = review(intake(payment='missing', filing=filing))
    assert current.page()['title'] == f'Was your last payment after {cutoff}?'
    before = deepcopy(current.__dict__)
    feedback = ' '.join(current.page()['answer_responses'][answer])
    assert ack in feedback and cutoff in feedback
    assert current.__dict__ == before
    following = advance_updated(current, answer)
    assert following.current == ('statute_of_limitations_decision' if offered else SUMMARY)
    if offered:
        assert 'Consider raising this defense if your last payment was a year or more' in ' '.join(following.page()['body'])
    else:
        assert 'This defense does not apply' in feedback
        assert not following.session.checkbox_selections
        assert CONTENT['confirmation']['empty'] in following.page()['body']
    assert not following.session.defense_open_questions


@pytest.mark.parametrize('payment,offered', [('2025-09-20', True), ('2025-09-21', False)])
def test_agreed_payment_on_cutoff_is_qualifying(payment, offered):
    current = advance_updated(review(intake(payment=payment)), 'yes')
    assert current.current == ('statute_of_limitations_decision' if offered else SUMMARY)


@pytest.mark.parametrize('choices,pending', [
    ([], 'statute_of_limitations_decision'),
    (['no'], 'sol_checkboxes_first_third'),
    (['no', 'yes'], 'sol_checkbox_second'),
])
def test_shared_uncertainty_screen_next_returns_to_same_question(choices, pending):
    current = review(intake('buyer', oral='yes'))
    for choice in choices:
        current = advance_updated(current, choice)
    assert current.current == pending
    body = current.page()['body']
    assert current.page()['answer_responses']['unknown'] == []
    unresolved = advance_updated(current, 'unknown')
    page = unresolved.page()
    assert page['title'] == 'Ready to return to the pending question?'
    assert page['body'] == [CONTENT['shared_clarification']]
    assert [block['type'] for block in page['body_blocks']] == ['paragraph']
    assert page['input_type'] == 'continue' and page['next_label'] == 'Next'
    assert unresolved.session.defense_open_questions
    with pytest.raises(ValueError, match='Choose Next'):
        advance_updated(unresolved, 'unknown')
    returned = advance_updated(unresolved, 'continue')
    assert returned.current == pending and returned.page()['body'] == body
    assert returned.session.defense_open_questions
    decided = advance_updated(returned, 'no')
    assert not decided.session.defense_open_questions


@pytest.mark.parametrize('field,choices,resolver', [
    ('guided_creditor_type', [], 'sol_creditor_type_resolve'),
    ('guided_oral', ['yes', 'no'], 'sol_oral_gate_resolve'),
])
def test_unknown_shared_intake_goes_to_clarification_before_its_field(field, choices, resolver):
    history = intake('buyer', oral='yes')
    history = [a.model_copy(update={'value': 'unknown'}) if a.node_id == field else a for a in history]
    current = review(history)
    for choice in choices:
        current = advance_updated(current, choice)
    assert current.current == resolver
    assert current.page()['input_type'] == 'continue'
    returned = advance_updated(current, 'continue')
    assert returned.current == field
    unresolved = advance_updated(returned, 'unknown')
    assert unresolved.current == resolver
    assert unresolved.session.defense_open_questions
    returned = advance_updated(unresolved, 'continue')
    resolved = advance_updated(returned, 'buyer' if field == 'guided_creditor_type' else 'no')
    assert not resolved.session.defense_open_questions


def test_missing_filing_date_never_displays_an_unknown_cutoff():
    current = review(intake(filing='unknown', payment='missing'))
    assert current.current == 'sol_invalid_date_help'
    current = advance_updated(current, 'continue')
    assert current.current == 'guided_filing_date'
    current = advance_updated(current, '2024-02-29')
    assert current.page()['title'] == 'Was your last payment after 2023-02-28?'


def test_editing_after_cutoff_answer_removes_old_boxes_and_reopens_when_changed_back():
    history = intake(payment='missing') + answers(
        ('sol_payment_age', 'no'), ('statute_of_limitations_decision', 'yes'), ('sol_checkboxes_first_third', 'yes'), ('sol_written', 'continue'))
    updated = change(history, 'sol_payment_age', 'yes')
    assert updated.current == SUMMARY
    assert not updated.session.checkbox_selections.get(DEFENSE)
    assert all(not row['checked'] for row in updated.page()['rows'])
    reopened = change(updated.history, 'sol_payment_age', 'no', revision=updated.revision)
    assert reopened.current == 'statute_of_limitations_decision'
    assert not reopened.session.checkbox_selections.get(DEFENSE)


def test_debug_api_uses_v2_cutoff_and_shared_return_without_collecting(tmp_path):
    module = runpy.run_path(str(ROOT / 'scripts/guided_clickthrough_demo.py'))
    client = TestClient(module['create_app'](debug=True, collection_dir=tmp_path / 'research'))
    history = intake(payment='missing')
    state = client.post('/api/state', json={'history': [a.model_dump() for a in history]}).json()
    assert state['title'] == 'Was your last payment after 2025-09-20?'
    result = client.post('/api/advance', json={'history': [a.model_dump() for a in history], 'value': 'no'})
    assert result.status_code == 200
    assert result.json()['page']['title'] == 'Do you want to check off the Statute of Limitations checkbox?'
    uncertain = client.post('/api/advance', json={'history': result.json()['history'], 'value': 'unknown'})
    assert uncertain.status_code == 200
    assert uncertain.json()['page']['input_type'] == 'continue'
    returned = client.post('/api/advance', json={'history': uncertain.json()['history'], 'value': 'continue'})
    assert returned.status_code == 200
    assert returned.json()['page']['node_id'] == 'statute_of_limitations_decision'
    assert not (tmp_path / 'research').exists()


@pytest.mark.parametrize('previous_choice', ['yes', 'no'])
@pytest.mark.parametrize('timing', ['no', 'unknown'])
def test_revising_personal_timing_shows_main_choice_before_nested_choices(previous_choice, timing):
    history = intake(payment='missing') + answers(
        ('sol_payment_age', 'no'), ('statute_of_limitations_decision', previous_choice),
        ('sol_checkboxes_first_third', 'yes'), ('sol_written', 'continue'))
    current = change(history, 'sol_payment_age', timing)
    assert current.current == 'statute_of_limitations_decision'
    page = current.page()
    assert page['title'] == 'Do you want to check off the Statute of Limitations checkbox?'
    assert page['default_value'] == previous_choice
    assert 'Consider raising this defense' in ' '.join(page['body'])
    assert not current.session.checkbox_selections.get(DEFENSE)
    current = advance_updated(current, 'no' if previous_choice == 'yes' else 'yes')
    assert current.current == SUMMARY
    choices = current.session.checkbox_selections[DEFENSE]
    assert choices['main'] == ('exclude' if previous_choice == 'yes' else 'include')
    assert choices['first'] == choices['third'] == 'include'


@pytest.mark.parametrize('previous_timing', ['yes', 'no', 'unknown'])
@pytest.mark.parametrize('agreement', ['no', 'unknown'])
def test_revisiting_complaint_disagreement_always_asks_personal_timing(previous_timing, agreement):
    history = intake() + answers(('sol_payment_estimate_agree', 'no'), ('sol_payment_age', previous_timing))
    if previous_timing != 'yes':
        history += answers(('statute_of_limitations_decision', 'yes'), ('sol_checkboxes_first_third', 'yes'), ('sol_written', 'continue'))
    # Changing to agreement temporarily removes personal timing from the path.
    agreed = change(history, 'sol_payment_estimate_agree', 'yes')
    current = change(agreed.history, 'sol_payment_estimate_agree', agreement, revision=agreed.revision)
    assert current.current == 'sol_payment_age'
    assert current.page()['title'] == 'Was your last payment after 2025-09-20?'
    assert current.page()['default_value'] == previous_timing
    assert 'sol_payment_age' not in current.session.defense_answers
    assert not current.session.checkbox_selections.get(DEFENSE)
    # The new timing answer, rather than the cached answer, determines the route.
    recent = advance_updated(current, 'yes')
    assert recent.current == SUMMARY
    assert not recent.session.checkbox_selections.get(DEFENSE)
    qualifying = advance_updated(current, 'no')
    assert qualifying.current == 'statute_of_limitations_decision'


def test_disagreement_api_cannot_jump_over_a_saved_personal_timing_answer(tmp_path):
    module = runpy.run_path(str(ROOT / 'scripts/guided_clickthrough_demo.py'))
    client = TestClient(module['create_app'](debug=True, collection_dir=tmp_path / 'research'))
    history = intake() + answers(('sol_payment_estimate_agree', 'no'), ('sol_payment_age', 'yes'))
    result = client.post('/api/edit', json={
        'history': [a.model_dump() for a in history], 'edit_index': len(intake()), 'value': 'no',
    })
    assert result.status_code == 200
    payload = result.json()
    assert payload['page']['node_id'] == 'sol_payment_age'
    assert payload['history'][-1]['node_id'] == 'sol_payment_estimate_agree'
    state = client.post('/api/state', json={'history': payload['history'], 'revision': payload['revision']})
    assert state.status_code == 200
    assert state.json() == payload['page']
