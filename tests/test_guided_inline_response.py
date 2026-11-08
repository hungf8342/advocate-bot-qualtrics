"""Inline outcomes are draft evaluations; only Next commits an answer."""
from copy import deepcopy
import runpy
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from advocate_bot_qualtrics.practice_areas.consumer_debt.guided_sol import (
    COMPLETE, CONTENT, CONTINUE_PAGES, DEFENSES, GuidedSolReview, TREE,
)
from test_guided_sol import intake, review, advance_updated, default_answer, answers
from test_guided_november_scripts import reach, submit


@pytest.mark.parametrize('value,expected', [
    ('yes', 'You agree with the complaint'), ('no', None),
    ('unknown', 'You’re not sure how much time passed'),
])
def test_sol_non_checkbox_responses_stay_inline(value, expected):
    current = review(intake())
    before = deepcopy(current.__dict__)
    response = current.page()['answer_responses'][value]
    assert current.__dict__ == before
    if expected:
        assert expected in ' '.join(response)
    else:
        assert not response
    next_page = advance_updated(current, value).page()
    for text in response:
        assert text not in next_page['body']
    assert next_page['node_id'] != current.current


def test_new_choice_replaces_positive_negative_and_uncertain_outcomes_without_committing():
    current = reach('waiver')
    original = deepcopy(current.__dict__)
    responses = current.page()['answer_responses']
    assert 'This defense may apply' in ' '.join(responses['yes'])
    assert 'does not apply' in ' '.join(responses['no'])
    assert 'not sure' in ' '.join(responses['unknown'])
    assert current.__dict__ == original
    assert 'waiver' not in current.session.checkbox_selections
    offered = advance_updated(current, 'yes')
    assert offered.current == 'waiver_decision'
    assert offered.page()['body'] == []
    assert 'waiver' not in offered.session.checkbox_selections


@pytest.mark.parametrize('defense,node,values,phrase', [
    ('common_counts', 'common_counts_renege', ['no'], 'agreed to accept a lower payment'),
    ('excuse_breach', 'excuse_unconsented_change', [], 'changed the contract terms'),
    ('rescission', 'rescission_refuse_close', ['yes'], 'refused to grant your request'),
    ('accord_satisfaction', 'accord_compliance', [], 'agreement with'),
    ('oral_modification', 'oral_modification_agreement', [], 'during a conversation'),
    ('tender_payment', 'tender_payment_refused', [], 'refused to accept it'),
])
def test_eligibility_response_preamble_stays_with_its_screening_question(defense, node, values, phrase):
    current = submit(reach(defense), *values)
    assert current.current == node
    response = current.page()['answer_responses']['yes']
    assert phrase in ' '.join(response)
    following = advance_updated(current, 'yes')
    assert TREE.node(following.current).selection_checkboxes
    assert all(text not in following.page()['body'] for text in response)
    assert following.page()['title'].startswith('Do you want to check off')


def test_aggregate_laches_outcome_appears_on_last_fact_and_not_checkbox_question():
    current = submit(reach('laches'), 'no', 'no')
    assert current.current == 'laches_lost_info'
    responses = current.page()['answer_responses']
    assert 'Laches may apply' in ' '.join(responses['yes'])
    assert 'does not apply' in ' '.join(responses['no'])
    assert 'uncertain' in ' '.join(responses['unknown'])
    following = advance_updated(current, 'yes')
    assert following.current == 'laches_decision'
    assert 'Laches may apply if:' not in ' '.join(following.page()['body'])


def test_parent_outcome_is_inline_and_summary_keeps_the_checklist():
    current = submit(reach('excuse_breach'), 'no', 'no', 'no', 'no')
    assert current.current == 'excuse_fifth_checkbox'
    response = current.page()['answer_responses']['yes']
    assert 'Check off the overall' in ' '.join(response)
    following = advance_updated(current, 'yes')
    assert following.current == DEFENSES['excuse_breach']['summary']
    assert all(text not in following.page()['body'] for text in response)
    assert next(row for row in following.page()['rows'] if row['id'] == 'main')['checked']


def test_mitigation_outcomes_attach_to_their_own_fact_questions():
    current = reach('failure_to_mitigate', consolidation='yes')
    responses = current.page()['answer_responses']
    assert 'second indented checkbox does not apply' in ' '.join(responses['yes'])
    assert 'second indented checkbox may apply' in ' '.join(responses['no'])
    assert 'debt consolidation company' in ' '.join(responses['no'])
    current = submit(current, 'no')
    assert current.current == 'mitigation_settlement'
    assert 'first indented checkbox may apply' in ' '.join(current.page()['answer_responses']['yes'])
    current = submit(current, 'yes')
    assert current.current == 'mitigation_first_checkbox'
    assert current.page()['body'] == []
    # Deciding the first box does not repeat the earlier contact response.
    assert current.page()['answer_responses']['no'] == []
    current = submit(current, 'no')
    assert current.current == 'mitigation_second_checkbox'
    assert current.page()['body'] == []


def test_conditional_followup_keeps_only_new_question_text():
    current = submit(reach('lack_of_consideration'), 'no')
    assert current.current == 'consideration_other_user'
    assert current.page()['title'] == 'Did you open the account explicitly for another person to use?'
    assert current.page()['body'] == []


def test_general_guidance_remains_with_its_own_checkbox():
    current = reach('common_counts')
    assert 'miscalculate' in ' '.join(current.page()['body'])
    current = submit(reach('excuse_breach'), 'no')
    assert current.current == 'excuse_second_checkbox'
    assert 'miscalculate' in ' '.join(current.page()['body'])


def test_referral_response_is_inline_and_staff_confirmation_remains_required():
    current = submit(reach('capacity'), 'no', 'yes')
    response = current.page()['answer_responses']['no']
    assert 'Please raise your hand' in ' '.join(response)
    next_page = advance_updated(current, 'no')
    assert next_page.current == 'capacity_staff_help'
    assert all(text not in next_page.page()['body'] for text in response)
    assert advance_updated(next_page, 'unknown').current == 'capacity_staff_help'


def test_dynamic_language_preview_is_validated_and_never_changes_research_records(tmp_path):
    module = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'scripts/guided_clickthrough_demo.py'))
    app = module['create_app'](collection_dir=tmp_path)
    client = TestClient(app)
    current = reach('language_1632')
    sid = str(uuid4())
    history = [a.model_dump(mode='json') for a in current.history]
    assert client.post('/api/state', json={'history':history, 'session_id':sid}).status_code == 200
    before = {name: (tmp_path/name).read_bytes() for name in ['sessions.csv','defenses.csv','responses.csv','collection.sqlite3']}
    result = client.post('/api/preview', json={'history':history, 'value':'Spanish'})
    assert result.status_code == 200
    assert result.json()['node_id'] == 'language_primary'
    assert result.json()['response'] == ['You said that your primary language is Spanish.']
    assert result.json()['response_blocks'] == [{'type':'paragraph','text':'You said that your primary language is Spanish.'}]
    assert before == {name: (tmp_path/name).read_bytes() for name in before}
    assert client.post('/api/state', json={'history':history}).json()['node_id'] == 'language_primary'
    assert client.post('/api/preview', json={'history':history,'value':''}).status_code == 422
    question = review(intake())
    assert client.post('/api/preview', json={'history':[a.model_dump(mode='json') for a in question.history], 'value':'invalid'}).status_code == 422


@pytest.mark.parametrize('path', ['yes','no'])
def test_all_seventeen_sections_support_pure_previews_and_complete(path):
    current = review(intake('buyer', oral='yes'))
    seen = set()
    for _ in range(300):
        if current.current == COMPLETE:
            break
        seen.add(current._current_defense())
        before = deepcopy(current.__dict__)
        page = current.page()
        assert current.__dict__ == before
        if page['input_type'] == 'choice':
            assert set(page['answer_responses']) == {o['value'] for o in page['options']}
            for value, feedback in page['answer_responses'].items():
                assert feedback == current.preview_response(value)
                assert current.__dict__ == before
        value = 'continue' if current.current in CONTINUE_PAGES else path
        if page['input_type'] == 'text': value = 'Spanish'
        if current.current == 'language_contract': value = 'no'
        current = advance_updated(current, value)
    assert current.current == COMPLETE
    assert seen == set(DEFENSES)
    assert len(current.page()['groups']) == 17


@pytest.mark.parametrize('defense', ['unconscionable_contract'])
def test_broad_checkbox_confirmation_is_inline_before_review(defense):
    current = reach(defense)
    responses = current.page()['answer_responses']
    assert 'you’d like to check off' in ' '.join(responses['yes'])
    assert 'Check this box' in ' '.join(responses['yes'])
    assert 'don’t want to check off' in ' '.join(responses['no'])
    assert 'Leave unchecked' in ' '.join(responses['no'])
    following = advance_updated(current, 'yes')
    assert following.current == DEFENSES[defense]['summary']
    assert 'Review the checkbox selections below' in following.page()['body'][0]
    assert all(text not in following.page()['body'] for text in responses['yes'])


def test_chat_receives_inline_draft_as_unsubmitted_context(tmp_path):
    from advocate_bot_qualtrics.core.schemas import ChatTurnResponse
    module = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'scripts/guided_clickthrough_demo.py'))
    captured = []
    def model(**kwargs):
        captured.append(kwargs)
        return ChatTurnResponse(user_intent='ask_about_complaint', assistant_reply='This is the response to your draft answer.', next_node_id=None)
    module['create_app'].__globals__['submit_chat_turn'] = model
    client = TestClient(module['create_app'](collection_dir=tmp_path))
    current = reach('waiver')
    history = [a.model_dump(mode='json') for a in current.history]
    result = client.post('/api/help', json={'history':history,'question':'What does this response mean?','draft_value':'yes'})
    assert result.status_code == 200
    assert result.json()['next_node_id'] is None
    draft = captured[0]['payload']['draft_answer']
    assert draft['submitted'] is False and draft['value'] == 'yes'
    assert 'This defense may apply' in ' '.join(draft['response'])
    assert 'unsubmitted selection' in captured[0]['system']
    assert client.post('/api/state', json={'history':history}).json()['node_id'] == current.current


def test_sol_oral_guidance_stays_with_checkbox_after_resolving_preliminary_fact():
    current = review(intake(oral='unknown'))
    current = submit(current, 'yes', 'yes', 'yes')
    assert current.current == 'guided_oral'
    assert current.page()['answer_responses']['yes'] == []
    following = advance_updated(current, 'yes')
    assert following.current == 'sol_checkbox_second'
    assert 'Oral contracts have shorter statute of limitations' in ' '.join(following.page()['body'])


@pytest.mark.parametrize('creditor', ['original', 'buyer'])
def test_sol_main_checkbox_shares_page_with_its_complete_lead_in(creditor):
    current = review(intake(creditor))
    if creditor == 'original':
        assert 'You agree with the complaint' in ' '.join(current.page()['answer_responses']['yes'])
        assert 'Consider raising this defense' not in ' '.join(current.page()['answer_responses']['yes'])
        current = advance_updated(current, 'yes')
    assert current.current == 'statute_of_limitations_decision'
    page = current.page()
    body = ' '.join(page['body'])
    if creditor == 'original':
        assert 'You agree with the complaint' not in body
        assert 'Consider raising this defense' in body
        assert 'You think your last payment could be a year or more' in body
    else:
        assert 'Debt buyers often sue on older accounts' in body
        assert 'You are being sued by a debt buyer' in body
    assert page['title'] == 'Do you want to check off Statute of Limitations?'
    assert page['input_type'] == 'choice'


@pytest.mark.parametrize('timing', ['yes', 'unknown'])
def test_sol_personal_timing_lead_in_is_on_main_checkbox_page(timing):
    current = review(intake(payment='missing'))
    assert current.current == 'sol_payment_age'
    assert ('You said your last payment was' if timing == 'yes' else 'You’re not sure whether your last payment') in ' '.join(current.page()['answer_responses'][timing])
    assert 'Consider raising this defense' not in ' '.join(current.page()['answer_responses'][timing])
    current = advance_updated(current, timing)
    assert current.current == 'statute_of_limitations_decision'
    assert 'Consider raising this defense' in ' '.join(current.page()['body'])
    assert ('You said your last payment was' if timing == 'yes' else 'You’re not sure whether your last payment') not in ' '.join(current.page()['body'])


@pytest.mark.parametrize('main,group', [('yes','yes'), ('no','no')])
def test_sol_nested_checkbox_questions_keep_their_guidance(main, group):
    current = review(intake('buyer', oral='yes'))
    current = advance_updated(current, main)
    assert current.current == 'sol_checkboxes_first_third'
    assert 'first and third indented checkboxes' in ' '.join(current.page()['body'])
    assert current.page()['answer_responses'][group] == []
    current = advance_updated(current, group)
    assert current.current == 'sol_checkbox_second'
    assert 'Oral contracts have shorter statute of limitations' in ' '.join(current.page()['body'])
    assert 'contract with Original Example Bank was oral' in ' '.join(current.page()['body'])
    assert current.page()['title'].startswith('Do you want to check off the second indented')


@pytest.mark.parametrize('checkbox,lead_in,choices', [
    ('statute_of_limitations_decision', 'Debt buyers often sue on older accounts', []),
    ('sol_checkboxes_first_third', 'The statute of limitations periods differ', ['yes']),
    ('sol_checkbox_second', 'Oral contracts have shorter statute of limitations', ['yes','yes']),
])
def test_sol_checkbox_lead_in_survives_clarification_retry(checkbox,lead_in,choices):
    current = submit(review(intake('buyer',oral='yes')), *choices)
    assert current.current == checkbox
    expected = current.page()['body']
    assert lead_in in ' '.join(expected)
    current = advance_updated(current,'unknown')
    assert TREE.node(current.current).discussion_mode == 'questions'
    current = advance_updated(current,'retry')
    assert current.current == checkbox
    assert current.page()['body'] == expected


def test_sol_66_month_acknowledgment_is_inline_while_consider_guidance_stays_with_checkbox():
    current = review(intake(payment='2021-03-06'))
    original = deepcopy(current.__dict__)
    responses = current.page()['answer_responses']
    assert responses['yes'] == ['You agree with the complaint that your last payment was 66.5 months before the complaint was filed.']
    assert 'You agree' not in ' '.join(responses['no'])
    assert 'You agree' not in ' '.join(responses['unknown'])
    assert current.__dict__ == original
    following = advance_updated(current,'yes')
    assert following.current == 'statute_of_limitations_decision'
    body = following.page()['body']
    assert body[0].startswith('Consider raising this defense')
    assert '66.5' not in ' '.join(body)
    # Replaying Back restores the same inline acknowledgment for the saved choice.
    back = review(following.history[:-1])
    assert back.current == 'sol_payment_estimate_agree'
    assert back.page()['answer_responses']['yes'] == responses['yes']


@pytest.mark.parametrize('oral', ['yes','no'])
@pytest.mark.parametrize('selection', ['yes','no'])
def test_sol_first_third_selection_keeps_later_instruction_blocks_on_next_screen(oral,selection):
    current = submit(review(intake('buyer',oral=oral)), 'yes')
    assert current.current == 'sol_checkboxes_first_third'
    page = current.page()
    assert 'second indented checkbox' not in ' '.join(page['body'])
    assert page['answer_responses'][selection] == []
    following = advance_updated(current,selection)
    if oral == 'yes':
        assert following.current == 'sol_checkbox_second'
        assert 'Oral contracts have shorter statute of limitations' in ' '.join(following.page()['body'])
        assert 'Based on your answers' not in ' '.join(following.page()['body'])
        assert following.page()['answer_responses']['yes'] == []
        following = advance_updated(following,'yes')
    else:
        assert 'second indented checkbox does not apply' in ' '.join(following.page()['body'])
    assert following.current == DEFENSES['statute_of_limitations']['summary']
    assert 'Based on your answers to this defense section' in ' '.join(following.page()['body'])
    assert following.page()['rows']


@pytest.mark.parametrize('selection', ['yes','no'])
def test_ambiguity_explanation_and_confirmation_are_separate_screens(selection):
    current = reach('ambiguity')
    original = deepcopy(current.__dict__)
    page = current.page()
    assert 'Ambiguity means something is unclear' in ' '.join(page['body'])
    assert 'entire account history or contract' in ' '.join(page['body'])
    assert page['title'] == 'Ambiguity'
    assert page['body'][-1] == 'Do you want to check off Ambiguity?'
    assert page['answer_responses'][selection] == []
    assert current.__dict__ == original
    following = advance_updated(current,selection)
    assert following.current == DEFENSES['ambiguity']['summary']
    assert CONTENT['confirmation']['selected' if selection=='yes' else 'empty'] in following.page()['body']
    assert following.page()['rows'][0]['checked'] == (selection=='yes')
    assert 'ambiguity_decision' == following.history[following.page()['rows'][0]['edit_index']].node_id


def test_ambiguity_explanation_is_preserved_after_clarification_retry():
    current = reach('ambiguity')
    explanation = current.page()['body']
    current = submit(current,'unknown','retry')
    assert current.current == 'ambiguity_decision'
    assert current.page()['body'] == explanation
    assert current.page()['answer_responses']['no'] == []
    current = advance_updated(current,'no')
    assert current.current == DEFENSES['ambiguity']['summary']
    assert not current.session.defense_open_questions
