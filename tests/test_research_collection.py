"""Exercise CSV collection through the same HTTP workflow as the clickthrough."""
import csv
import runpy
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from advocate_bot_qualtrics.practice_areas.consumer_debt.research_collection import (
    DEFENSE_COLUMNS, RESPONSE_COLUMNS, SESSION_COLUMNS,
)
from test_clickthrough_workflow import (
    LACHES_SUMMARY, answers, both_defenses_history, completed_history, intake, laches_history,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def collector(tmp_path):
    module = runpy.run_path(str(ROOT / 'scripts/run_clickthrough.py'))
    app = module['create_app'](collection_dir=tmp_path)
    client = TestClient(app)
    sid = str(uuid4())
    assert client.post('/api/state', json={'session_id': sid}).status_code == 200
    return client, tmp_path, sid, module


def rows(directory, filename):
    with (directory / filename).open(newline='', encoding='utf-8') as handle:
        return list(csv.DictReader(handle))


def context(sid):
    return dict(session_id=sid, event_id=str(uuid4()),
                displayed_at='2026-11-03T10:00:00-08:00', checked_at='2026-11-03T10:00:01-08:00',
                ended_at='2026-11-03T10:00:02-08:00')


def advance(client, sid, history, revision=None, value=None):
    result = client.post('/api/advance', json={
        'history': [a.model_dump(mode='json') for a in history], 'revision': revision,
        'value': value, 'collection': context(sid)})
    assert result.status_code == 200, result.text
    return result.json()


def run_history(client, sid, history):
    result = None
    for index, answer in enumerate(history):
        result = advance(client, sid, history[:index], value=answer.value)
    return result


def edit(client, sid, result, node, value):
    index = next(i for i, a in enumerate(result['history']) if a['node_id'] == node)
    response = client.post('/api/edit', json={
        'history': result['history'], 'revision': result['revision'], 'edit_index': index,
        'value': value, 'collection': context(sid)})
    assert response.status_code == 200, response.text
    return response.json()


def test_headers_completion_exit_and_restart_persistence(collector):
    client, directory, sid, module = collector
    for filename, headers in [('sessions.csv', SESSION_COLUMNS), ('defenses.csv', DEFENSE_COLUMNS),
                              ('responses.csv', RESPONSE_COLUMNS)]:
        with (directory / filename).open() as handle:
            assert next(csv.reader(handle)) == headers
    assert rows(directory, 'sessions.csv')[0]['SESSION.COMPLETED'] == 'No'
    run_history(client, sid, both_defenses_history())
    session = rows(directory, 'sessions.csv')[0]
    assert session['SESSION.COMPLETED'] == 'Yes'
    assert session['SESSION.END.TIME'] == ''
    assert session['SESSION.TREE.VERSION'].startswith('guided-17-defenses-2026-11-10-')
    assert client.post('/api/collection/end', json={'session_id': sid}).status_code == 200
    assert datetime.fromisoformat(rows(directory, 'sessions.csv')[0]['SESSION.END.TIME']).tzinfo
    module['create_app'](collection_dir=directory)
    assert rows(directory, 'sessions.csv')[0]['SESSION.COMPLETED'] == 'Yes'
    defense = rows(directory, 'defenses.csv')[0]
    from advocate_bot_qualtrics.practice_areas.consumer_debt.workflow import DEFENSES
    assert len(DEFENSES) == 17
    for name in DEFENSES:
        assert defense[f'DEFENSE.{name}.CHECKED'] in {'Yes', 'No'}
        assert defense[f'DEFENSE.{name}.TREE.PROJECTION'] in {'Yes', 'No'}
    assert 'DEFENSE.identity_theft.CHECKED' not in defense
    for name, checked, projection in [('statute_of_limitations', 'Yes', 'Yes'),
        ('ambiguity', 'Yes', 'Yes'), ('laches', 'No', 'No')]:
        assert defense[f'DEFENSE.{name}.CHECKED'] == checked
        assert defense[f'DEFENSE.{name}.TREE.PROJECTION'] == projection
        assert defense[f'DEFENSE.{name}.CHANGED'] == '0'


def test_input_timing_derived_value_calculations_and_csv_quoting(collector):
    client, directory, sid, _ = collector
    history = intake()
    history = [a.model_copy(update={'value': 'Bank, "One"'}) if a.node_id == 'guided_plaintiff' else a for a in history]
    run_history(client, sid, history)
    events = rows(directory, 'responses.csv')
    name = next(r for r in events if r['RESPONSE.ITEM.ID'] == 'PLAINTIFF')
    assert name['RESPONSE.ITEM.VALUE'] == 'Bank, "One"'
    assert name['RESPONSE.EVENT.TYPE'] == 'First submission'
    assert name['RESPONSE.REVISION.NUMBER'] == '0'
    assert 'RESPONSE.CALC.OR.INPUT' not in name
    assert name['RESPONSE.CHECK.TIME'] == '2026-11-03T18:00:01.000+00:00'
    assert name['RESPONSE.START.TIME'] == '2026-11-03T18:00:00.000+00:00'
    assert name['RESPONSE.END.TIME'] == '2026-11-03T18:00:02.000+00:00'
    original = next(r for r in events if r['RESPONSE.ITEM.ID'] == 'ORIGINAL.CREDITOR')
    assert original['RESPONSE.EVENT.TYPE'] == 'Program calculation'
    assert original['RESPONSE.ITEM.VALUE'] == name['RESPONSE.ITEM.VALUE']
    assert any(r['RESPONSE.ITEM.ID'] == 'sol_creditor_type' and
               r['RESPONSE.EVENT.TYPE'] == 'Program calculation' for r in events)


def test_edits_invalidation_revisions_and_fresh_checkbox_answer(collector):
    client, directory, sid, _ = collector
    history = laches_history() + answers(('laches', 'yes'), ('laches_statements', 'no'),
        ('laches_lost_info', 'no'), ('laches_decision', 'yes'), (LACHES_SUMMARY, 'continue'))
    result = run_history(client, sid, history)
    result = edit(client, sid, result, 'laches', 'no')
    defense = rows(directory, 'defenses.csv')[0]
    assert defense['DEFENSE.laches.CHECKED'] == 'No'
    assert defense['DEFENSE.laches.TREE.PROJECTION'] == 'No'
    assert defense['DEFENSE.laches.CHANGED'] == '1'
    assert defense['DEFENSE.statute_of_limitations.CHANGED'] == '0'
    invalidations = [r for r in rows(directory, 'responses.csv') if r['RESPONSE.ITEM.ID'] == 'laches_decision']
    assert [r['RESPONSE.EVENT.TYPE'] for r in invalidations] == ['First submission', 'Program invalidation']
    assert invalidations[-1]['RESPONSE.CHECK.TIME'] == 'NA'
    assert invalidations[-1]['RESPONSE.ITEM.VALUE'] == ''
    assert rows(directory, 'sessions.csv')[0]['SESSION.COMPLETED'] == 'No'
    assert result['page']['node_id'] == 'laches_finish'
    result = step(client, sid, result, 'continue')
    result = edit(client, sid, result, 'laches', 'yes')
    from advocate_bot_qualtrics.practice_areas.consumer_debt.workflow import GuidedAnswer
    advance(client, sid, [GuidedAnswer(**a) for a in result['history']], result['revision'], 'no')
    events = [r for r in rows(directory, 'responses.csv') if r['RESPONSE.ITEM.ID'] == 'laches_decision']
    assert events[-1]['RESPONSE.EVENT.TYPE'] == 'User change'
    assert events[-1]['RESPONSE.CHECK.TIME'] == '2026-11-03T18:00:01.000+00:00'
    assert events[-1]['RESPONSE.REVISION.NUMBER'] == '2'


def test_noop_edit_and_navigation_do_not_change_or_invalidate_retained_answers(collector):
    client, directory, sid, _ = collector
    result = run_history(client, sid, both_defenses_history())
    before = rows(directory, 'responses.csv')
    client.post('/api/state', json={'session_id': sid, 'history': result['history'][:3]})
    assert rows(directory, 'responses.csv') == before
    result = edit(client, sid, result, 'guided_plaintiff', 'Example Bank')
    assert rows(directory, 'responses.csv') == before
    result = edit(client, sid, result, 'guided_plaintiff', 'New Bank')
    events = rows(directory, 'responses.csv')[len(before):]
    assert not any(r['RESPONSE.EVENT.TYPE'] == 'Program invalidation' for r in events)
    assert rows(directory, 'defenses.csv')[0]['DEFENSE.ambiguity.CHECKED'] == 'Yes'


def test_isolation_abandonment_duplicate_delivery_and_validation(collector):
    client, directory, sid, _ = collector
    payload = {'history': [], 'value': 'continue', 'collection': context(sid)}
    assert client.post('/api/advance', json=payload).status_code == 200
    before = rows(directory, 'responses.csv')
    assert client.post('/api/advance', json=payload).status_code == 200
    assert rows(directory, 'responses.csv') == before
    payload['value'] = 'invalid'
    assert client.post('/api/advance', json=payload).status_code == 422
    assert rows(directory, 'responses.csv') == before
    sid2 = str(uuid4())
    client.post('/api/state', json={'session_id': sid2})
    client.post('/api/collection/end', json={'session_id': sid2})
    sessions = rows(directory, 'sessions.csv')
    assert len(sessions) == len(rows(directory, 'defenses.csv')) == 2
    assert sessions[1]['SESSION.COMPLETED'] == 'No'
    assert sessions[1]['SESSION.END.TIME']
    assert not sessions[0]['SESSION.END.TIME']
    bad = context(sid)
    bad['ended_at'] = '2026-11-03T09:00:00-08:00'
    payload.update(value='continue', collection=bad)
    assert client.post('/api/advance', json=payload).status_code == 422


def test_new_required_question_does_not_invalidate_pending_later_defenses(collector):
    client, directory, sid, _ = collector
    result = run_history(client, sid, both_defenses_history())
    before = len(rows(directory, 'responses.csv'))
    result = edit(client, sid, result, 'guided_oral', 'yes')
    assert result['page']['node_id'] == 'sol_checkbox_second'
    new_events = rows(directory, 'responses.csv')[before:]
    assert not any(r['RESPONSE.ITEM.ID'] in {'ambiguity_decision', 'laches', 'laches_statements',
                                           'laches_lost_info', 'identity_recognize'}
                   and r['RESPONSE.EVENT.TYPE'] == 'Program invalidation' for r in new_events)
    defense = rows(directory, 'defenses.csv')[0]
    assert defense['DEFENSE.ambiguity.CHECKED'] == 'Yes'
    assert defense['DEFENSE.statute_of_limitations.CHANGED'] == '1'


def test_projection_yes_does_not_require_selecting_a_checkbox(collector):
    client, directory, sid, _ = collector
    history = completed_history('buyer')
    history = [a.model_copy(update={'value': 'no'}) if a.node_id in
               {'statute_of_limitations_decision', 'sol_checkboxes_first_third'} else a for a in history]
    run_history(client, sid, history)
    defense = rows(directory, 'defenses.csv')[0]
    assert defense['DEFENSE.statute_of_limitations.CHECKED'] == 'No'
    assert defense['DEFENSE.statute_of_limitations.TREE.PROJECTION'] == 'Yes'


def test_reload_reopens_same_session_and_preserves_early_exit_during_a_submission(collector):
    client, directory, sid, _ = collector
    client.post('/api/collection/end', json={'session_id': sid})
    ended = rows(directory, 'sessions.csv')[0]['SESSION.END.TIME']
    advance(client, sid, [], value='continue')
    assert rows(directory, 'sessions.csv')[0]['SESSION.END.TIME'] == ended
    client.post('/api/state', json={'session_id': sid})
    assert len(rows(directory, 'sessions.csv')) == 1
    assert rows(directory, 'sessions.csv')[0]['SESSION.END.TIME'] == ''


def test_defense_fields_are_absent_until_their_individual_results_are_known(collector):
    client, directory, sid, _ = collector
    result = run_history(client, sid, intake())
    assert not any(r['RESPONSE.ITEM.ID'].startswith('DEFENSE.') for r in rows(directory, 'responses.csv'))
    for name in ('statute_of_limitations', 'ambiguity', 'laches', 'mistake', 'common_counts', 'capacity', 'language_1632'):
        defense = rows(directory, 'defenses.csv')[0]
        assert defense[f'DEFENSE.{name}.CHECKED'] == ''
        assert defense[f'DEFENSE.{name}.TREE.PROJECTION'] == ''
    assert result['page']['node_id'] == 'sol_payment_estimate_agree'


def test_response_schema_event_categories_and_program_check_times(collector):
    client, directory, sid, _ = collector
    result = run_history(client, sid, both_defenses_history())
    edit(client, sid, result, 'ambiguity_decision', 'no')
    events = rows(directory, 'responses.csv')
    assert list(events[0]) == ['SESSION.ID', 'RESPONSE.ITEM.ID', 'RESPONSE.ITEM.VALUE',
        'RESPONSE.EVENT.TYPE', 'RESPONSE.REVISION.NUMBER', 'RESPONSE.START.TIME',
        'RESPONSE.CHECK.TIME', 'RESPONSE.END.TIME']
    allowed = {'First submission', 'User change', 'Program calculation', 'Program invalidation'}
    for record in events:
        assert record['RESPONSE.EVENT.TYPE'] in allowed
        if record['RESPONSE.EVENT.TYPE'].startswith('Program '):
            assert record['RESPONSE.CHECK.TIME'] == 'NA'
            assert record['RESPONSE.START.TIME'] == record['RESPONSE.END.TIME']
        else:
            assert record['RESPONSE.START.TIME'] < record['RESPONSE.CHECK.TIME'] < record['RESPONSE.END.TIME']
    assert any(r['RESPONSE.EVENT.TYPE'] == 'User change' for r in events)


@pytest.mark.parametrize('checked', ['2026-11-03T09:59:59-08:00',
                                    '2026-11-03T10:00:03-08:00', '2026-11-03T10:00:01'])
def test_invalid_answer_check_times_are_rejected_without_recording(collector, checked):
    client, directory, sid, _ = collector
    advance(client, sid, [], value='continue')
    before = rows(directory, 'responses.csv')
    metadata = context(sid)
    metadata['checked_at'] = checked
    response = client.post('/api/advance', json={'history': [{'node_id': 'guided_welcome', 'value': 'continue'}],
        'value': 'Case 1', 'collection': metadata})
    assert response.status_code == 422
    assert rows(directory, 'responses.csv') == before


def test_accepting_prefilled_answer_without_checking_records_na(collector):
    client, directory, sid, _ = collector
    advance(client, sid, [], value='continue')
    metadata = context(sid)
    metadata['checked_at'] = None
    response = client.post('/api/advance', json={'history': [{'node_id': 'guided_welcome', 'value': 'continue'}],
        'value': 'Case 1', 'collection': metadata})
    assert response.status_code == 200
    event = rows(directory, 'responses.csv')[0]
    assert event['RESPONSE.EVENT.TYPE'] == 'First submission'
    assert event['RESPONSE.CHECK.TIME'] == 'NA'


def defense_events(directory, defense, field):
    return [r for r in rows(directory, 'responses.csv')
            if r['RESPONSE.ITEM.ID'] == f'DEFENSE.{defense}.{field}']


def step(client, sid, result, value):
    from advocate_bot_qualtrics.practice_areas.consumer_debt.workflow import GuidedAnswer
    return advance(client, sid, [GuidedAnswer(**a) for a in result['history']], result['revision'], value)


@pytest.mark.parametrize('choice', ['yes', 'no'])
def test_sol_projection_precedes_explicit_checkbox_choice(collector, choice):
    client, directory, sid, _ = collector
    result = run_history(client, sid, intake())
    assert not defense_events(directory, 'statute_of_limitations', 'TREE.PROJECTION')
    result = step(client, sid, result, 'yes')  # Agree to the qualifying payment date.
    assert result['page']['node_id'] == 'statute_of_limitations_decision'
    projection = defense_events(directory, 'statute_of_limitations', 'TREE.PROJECTION')
    assert [r['RESPONSE.ITEM.VALUE'] for r in projection] == ['Yes']
    assert projection[0]['RESPONSE.REVISION.NUMBER'] == '0'
    assert not defense_events(directory, 'statute_of_limitations', 'CHECKED')
    result = step(client, sid, result, choice)
    selections = defense_events(directory, 'statute_of_limitations', 'CHECKED')
    if choice == 'yes':
        assert [r['RESPONSE.ITEM.VALUE'] for r in selections] == ['Yes']
    else:
        assert selections == []  # Indented boxes still require answers.
        result = step(client, sid, result, 'no')
        assert [r['RESPONSE.ITEM.VALUE'] for r in
                defense_events(directory, 'statute_of_limitations', 'CHECKED')] == ['No']


def test_sol_unchecked_result_waits_for_the_oral_checkbox(collector):
    client, directory, sid, _ = collector
    result = run_history(client, sid, intake('buyer', oral='yes'))
    result = step(client, sid, result, 'no')
    result = step(client, sid, result, 'no')
    assert result['page']['node_id'] == 'sol_checkbox_second'
    assert not defense_events(directory, 'statute_of_limitations', 'CHECKED')
    step(client, sid, result, 'no')
    assert [r['RESPONSE.ITEM.VALUE'] for r in
            defense_events(directory, 'statute_of_limitations', 'CHECKED')] == ['No']


def test_no_offer_result_records_no_only_after_the_tree_finishes_screening(collector):
    client, directory, sid, _ = collector
    result = run_history(client, sid, intake(payment='2026-07-01'))
    assert not defense_events(directory, 'statute_of_limitations', 'TREE.PROJECTION')
    assert not defense_events(directory, 'statute_of_limitations', 'CHECKED')
    result = step(client, sid, result, 'yes')
    assert result['page']['input_type'] == 'summary'
    for field in ('TREE.PROJECTION', 'CHECKED'):
        events = defense_events(directory, 'statute_of_limitations', field)
        assert [r['RESPONSE.ITEM.VALUE'] for r in events] == ['No']
        assert events[0]['RESPONSE.REVISION.NUMBER'] == '0'


@pytest.mark.parametrize('fact,choice', [('yes', 'yes'), ('yes', 'no'), ('no', None)])
def test_laches_waits_for_offer_result_and_checkbox_choice(collector, fact, choice):
    client, directory, sid, _ = collector
    result = run_history(client, sid, laches_history())
    assert not defense_events(directory, 'laches', 'TREE.PROJECTION')
    assert not defense_events(directory, 'laches', 'CHECKED')
    for answer in (fact, 'no'):
        result = step(client, sid, result, answer)
        assert not defense_events(directory, 'laches', 'TREE.PROJECTION')
        assert not defense_events(directory, 'laches', 'CHECKED')
    result = step(client, sid, result, 'no')
    projected = 'Yes' if fact == 'yes' else 'No'
    assert [r['RESPONSE.ITEM.VALUE'] for r in
            defense_events(directory, 'laches', 'TREE.PROJECTION')] == [projected]
    if choice:
        assert not defense_events(directory, 'laches', 'CHECKED')
        step(client, sid, result, choice)
    assert [r['RESPONSE.ITEM.VALUE'] for r in defense_events(directory, 'laches', 'CHECKED')] == [
        'Yes' if choice == 'yes' else 'No']


def test_unknown_checkbox_answer_is_not_recorded_as_unchecked(collector):
    client, directory, sid, _ = collector
    result = run_history(client, sid, intake('buyer'))
    result = step(client, sid, result, 'unknown')
    assert not defense_events(directory, 'statute_of_limitations', 'CHECKED')
    assert rows(directory, 'defenses.csv')[0]['DEFENSE.statute_of_limitations.CHECKED'] == ''


def test_reopening_screening_invalidates_results_instead_of_recording_false_no(collector):
    client, directory, sid, _ = collector
    result = run_history(client, sid, both_defenses_history())
    result = edit(client, sid, result, 'guided_filing_date', '2026-10-01')
    # A previously agreed exact date can remain reusable; changing it across the
    # timing threshold requires a new payment-date confirmation.
    result = edit(client, sid, result, 'guided_payment_date', '2026-09-01')
    assert result['page']['node_id'] == 'sol_payment_estimate_agree'
    for field in ('CHECKED', 'TREE.PROJECTION'):
        events = defense_events(directory, 'statute_of_limitations', field)
        assert events[-1]['RESPONSE.EVENT.TYPE'] == 'Program invalidation'
        assert events[-1]['RESPONSE.ITEM.VALUE'] == ''
        assert rows(directory, 'defenses.csv')[0][f'DEFENSE.statute_of_limitations.{field}'] == ''
    result = step(client, sid, result, 'yes')
    for field in ('CHECKED', 'TREE.PROJECTION'):
        events = defense_events(directory, 'statute_of_limitations', field)
        assert events[-1]['RESPONSE.EVENT.TYPE'] == 'Program calculation'
        assert events[-1]['RESPONSE.ITEM.VALUE'] == 'No'
