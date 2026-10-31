"""The separate guided prototype reuses SOL routing and replays changed answers."""
import runpy
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from advocate_bot_qualtrics.core.schemas import ChatTurnResponse
from advocate_bot_qualtrics.practice_areas.consumer_debt.guided_sol import (
    AMBIGUITY_SUMMARY, IDENTITY_INTRO, IDENTITY_SUMMARY, LACHES_INTRO, LACHES_SUMMARY, BOX_LABELS, COMPLETE, PRELIMINARY_FIELDS, PRELIMINARY_SUMMARY, SOL_INTRO, SUMMARY, GuidedAnswer, GuidedSolReview,
)
from advocate_bot_qualtrics.practice_areas.consumer_debt.tree import INTERACTIVE_TREE_DEFINITION as TREE

ROOT = Path(__file__).resolve().parents[1]


def answers(*pairs):
    return [GuidedAnswer(node_id=node, value=value) for node, value in pairs]


def intake(creditor='original', payment='2024-03-15', filing='2026-09-20', oral='no'):
    values = {'guided_case_number': '26CV-EXAMPLE', 'guided_plaintiff': 'Example Bank',
              'guided_creditor_type': creditor, 'guided_original_creditor': 'Original Example Bank',
              'guided_law_firm': 'Example Law Firm', 'guided_suit_type': 'breach', 'guided_amount': '4250.00',
              'guided_payment_date': payment, 'guided_open_date': '2017-08-20', 'guided_filing_date': filing,
              'guided_breach_date': 'missing', 'guided_statement': 'yes', 'guided_ownership_claim': 'yes',
              'guided_ownership_proof': 'no', 'guided_verified': 'no', 'guided_consolidation': 'no',
              'guided_recognize': 'yes', 'guided_oral': oral}
    history = answers(('guided_welcome', 'continue'))
    for node in PRELIMINARY_FIELDS:
        if node == 'guided_original_creditor' and creditor == 'original':
            continue
        history += answers((node, values[node]))
    return history + answers((PRELIMINARY_SUMMARY, 'continue'), (SOL_INTRO, 'continue'))


def review(history):
    return GuidedSolReview().replay(history)


def test_opening_overview_has_requested_text_and_continues_to_preliminary_fields():
    current = GuidedSolReview()
    page = current.page()
    assert page['title'] == 'Overview'
    assert page['body'] == [
        'To finish your answer, you will check off what defenses apply to your lawsuit, using a form called Attachment 4. '
        'This clickthrough tool will help you decide whether to check off each defense or not.',
        'First, the tool will ask you to verify some details about your case. Then, it will ask additional questions and guide you through '
        'the 21 defenses on Attachment 4 in order. Fill out each defense in Attachment 4 as recorded in the clickthrough tool.',
    ]
    assert 'This prototype currently includes' in page['why']
    assert page['input_type'] == 'continue'
    assert not current.session.preliminary_fields
    assert review(answers(('guided_welcome', 'continue'))).current == 'guided_case_number'


def test_prefilled_examples_are_not_effective_facts_until_confirmed():
    guided = GuidedSolReview({'PLAINTIFF':'Prefilled Bank','COMPLAINT.DATE':'2026-09-20'})
    assert not guided.session.preliminary_fields
    guided.replay(answers(('guided_welcome','continue'), ('guided_case_number','26CV-EXAMPLE')))
    assert guided.page()['default_value']=='Prefilled Bank'
    assert 'PLAINTIFF-NAME' not in guided.session.preliminary_fields


@pytest.mark.parametrize('creditor', ['original', 'buyer', 'unknown'])
def test_sol_has_a_dedicated_general_explanation_after_preliminary_review(creditor):
    from advocate_bot_qualtrics.practice_areas.consumer_debt.guided_sol import CONTENT
    history = intake(creditor)[:-1]
    current = review(history)
    assert current.current == SOL_INTRO
    explanation = CONTENT['nodes']['statute_of_limitations_intro']['explanation'].replace('[PLAINTIFF]', 'Example Bank')
    assert current.page()['body'] == [explanation]
    assert current.page()['section'] == 'Statute of Limitations'
    assert current.page()['section_number'] == 2


def test_preliminary_section_covers_the_october_30_fields_and_has_its_own_summary():
    history = intake()[:-2]
    current = review(history)
    assert current.current == PRELIMINARY_SUMMARY
    page = current.page()
    assert page['section'] == 'Preliminary fields'
    assert page['section_number'] == 1 and page['progress_stage'] == 0
    assert page['input_type'] == 'preliminary_summary'
    assert len(PRELIMINARY_FIELDS) == len(page['case_details']) == 18
    assert not current.session.checkbox_selections and not current.session.script_visited
    assert current.session.original_creditor == current.session.plaintiff_name == 'Example Bank'
    original = next(d for d in page['case_details'] if d['label'] == 'Original creditor')
    assert original['derived'] and original['edit_index'] is None
    assert 'guided_original_creditor' not in {a.node_id for a in history}
    assert current.session.preliminary_fields['SUIT-TYPE'].value == 'breach'
    assert current.session.preliminary_fields['RECOGNIZE'].value == 'yes'


@pytest.mark.parametrize('creditor', ['original', 'buyer'])
def test_known_preliminary_values_are_not_requested_again_in_defense_sections(creditor):
    history = both_defenses_history(completed_history(creditor, oral='yes'))
    cutoff = next(i for i, a in enumerate(history) if a.node_id == SOL_INTRO)
    assert not any(a.node_id in PRELIMINARY_FIELDS for a in history[cutoff+1:])
    current = review(history)
    assert current.session.filing_date == date(2026, 9, 20)
    assert current.session.preliminary_fields['ORAL'].value == 'yes'
    assert current.session.preliminary_fields['PLAINTIFF'].value == creditor
    assert 'sol_creditor_type_resolve' not in current.session.defense_answers
    assert 'sol_oral_gate_resolve' not in current.session.defense_answers


def test_unresolved_preliminary_answer_returns_to_its_own_section():
    current = review(intake('unknown'))
    assert current.current == 'guided_creditor_type'
    assert current.page()['section'] == 'Preliminary fields'
    assert 'still unresolved' in current.page()['body'][0]
    current = advance_updated(current, 'original')
    assert current.current == 'sol_payment_estimate_agree'
    assert current.page()['section'] == 'Statute of Limitations'
    # Oral status is irrelevant on an ineligible timing path.
    current = review(intake(payment='2026-07-01', oral='unknown') + answers(('sol_payment_estimate_agree', 'yes')))
    assert current.current == SUMMARY


@pytest.mark.parametrize('node,value', [('guided_case_number', '26CV-NEW'), ('guided_amount', '900.50'),
                                      ('guided_statement', 'no'), ('guided_suit_type', 'both'),
                                      ('guided_consolidation', 'yes'), ('guided_recognize', 'no')])
def test_editing_unrelated_preliminary_fields_preserves_both_defense_choices(node, value):
    history = both_defenses_history()
    current = change(history, node, value)
    assert current.current == SUMMARY
    assert current.page()['changes'] == []
    current = advance_updated(current, 'continue')
    assert current.current == AMBIGUITY_SUMMARY
    assert current.session.checkbox_selections == review(history).session.checkbox_selections


def test_editing_before_defense_review_stays_at_preliminary_summary():
    history = intake()[:-2]
    current = change(history, 'guided_case_number', '26CV-CORRECTED')
    assert current.current == PRELIMINARY_SUMMARY
    assert not current.session.script_visited
    current = advance_updated(current, 'continue')
    assert current.current == SOL_INTRO
    assert not current.session.script_visited


@pytest.mark.parametrize('node,value', [('guided_amount', '0'), ('guided_amount', '-1'), ('guided_amount', 'NaN'),
                                      ('guided_amount', '12.345'), ('guided_amount', 'not money'),
                                      ('guided_open_date', '2026-02-30'), ('guided_suit_type', 'neither'),
                                      ('guided_statement', 'maybe')])
def test_preliminary_formats_are_validated_before_advancing(node, value):
    history = intake()
    index = next(i for i, a in enumerate(history) if a.node_id == node)
    with pytest.raises(ValueError):
        review(history[:index] + answers((node, value)))


def test_preliminary_default_formats_and_approved_help():
    defaults = {'CASE.NUMBER': '26CV-DEFAULT', 'PLAINTIFF': 'Default Bank', 'AMOUNT': '$4,250.00', 'STATEMENT': True}
    history = intake()
    for node, default in [('guided_amount', '4250.00'), ('guided_statement', 'yes')]:
        index = next(i for i, a in enumerate(history) if a.node_id == node)
        current = GuidedSolReview(defaults).replay(history[:index])
        assert current.page()['default_value'] == default
    index = next(i for i, a in enumerate(history) if a.node_id == 'guided_oral')
    page = review(history[:index]).page()
    assert 'Not remembering a signature' in page['help_text']
    assert page['title'] == 'Did you open this account orally, with no written contract?'


def review_nodes(current):
    return [row['node_id'] for row in current.page()['review_answers']]


@pytest.mark.parametrize('oral', ['yes', 'no'])
def test_buyer_review_shows_only_active_fields_while_all_case_details_remain_available(oral):
    current = review(completed_history('buyer', oral=oral))
    assert review_nodes(current) == ['guided_creditor_type', 'guided_oral']
    assert len(current.page()['case_details']) == 18


def test_agreed_date_review_includes_exact_timing_evidence_and_no_personalization():
    current = review(completed_history())
    assert review_nodes(current) == ['guided_creditor_type', 'guided_payment_date', 'guided_filing_date',
                                     'sol_payment_estimate_agree', 'guided_oral']
    assert next(r for r in current.page()['review_answers'] if r['node_id'] == 'sol_payment_estimate_agree')['value'] == 'Yes'


@pytest.mark.parametrize('agreement,payment', [('no', '2024-03-15'), ('unknown', '2024-03-15'), (None, 'missing')])
@pytest.mark.parametrize('timing', ['yes', 'no', 'unknown'])
def test_personal_timing_review_excludes_discarded_complaint_date(agreement, payment, timing):
    history = intake(payment=payment)
    if agreement:
        history += answers(('sol_payment_estimate_agree', agreement))
    history += answers(('sol_payment_age', timing))
    if timing != 'no':
        history += answers(('statute_of_limitations_decision', 'no'), ('sol_checkboxes_first_third', 'no'))
    current = review(history)
    expected = ['guided_creditor_type', 'guided_filing_date', 'sol_payment_age']
    if timing != 'no':
        expected += ['guided_oral']
    assert review_nodes(current) == expected
    timing_row = next(row for row in current.page()['review_answers'] if row['node_id'] == 'sol_payment_age')
    assert timing_row['value'] == {'yes': 'Yes', 'no': 'No', 'unknown': 'Not sure'}[timing]
    assert history[timing_row['edit_index']].node_id == 'sol_payment_age'


def test_ineligible_timing_review_does_not_include_oral_status():
    current = review(intake(payment='2026-07-01', oral='unknown') + answers(('sol_payment_estimate_agree', 'yes')))
    assert current.current == SUMMARY
    assert review_nodes(current) == ['guided_creditor_type', 'guided_payment_date', 'guided_filing_date', 'sol_payment_estimate_agree']


def test_ambiguity_review_has_no_preliminary_dependencies_and_final_review_is_filtered():
    current = review(both_defenses_history(complete=False))
    assert current.current == AMBIGUITY_SUMMARY
    assert current.page()['review_answers'] == []
    assert len(current.page()['case_details']) == 18
    complete = review(both_defenses_history(completed_history('buyer')))
    assert review_nodes(complete) == ['guided_creditor_type', 'guided_oral', 'guided_recognize', 'laches', 'laches_statements', 'laches_lost_info']


def test_retained_comparison_review_does_not_claim_agreement_with_the_edited_date():
    current = change(completed_history(), 'guided_payment_date', '2024-04-15')
    assert current.current == SUMMARY
    assert review_nodes(current) == ['guided_creditor_type', 'guided_payment_date', 'guided_filing_date', 'guided_oral']
    payment = next(row for row in current.page()['review_answers'] if row['node_id'] == 'guided_payment_date')
    assert payment['value'] == 'Apr 15, 2024'


def test_original_path_matches_script_and_combines_first_and_third():
    history=intake()
    current=review(history)
    assert current.current=='sol_payment_estimate_agree'
    assert current.page()['visual']['months']==30.2
    assert current.session.filing_date==date(2026,9,20)
    history += answers(('sol_payment_estimate_agree','yes'))
    assert review(history).current=='statute_of_limitations_decision'
    history += answers(('statute_of_limitations_decision','no'),('sol_checkboxes_first_third','yes'))
    current=review(history)
    assert current.current==SUMMARY
    assert current.session.checkbox_selections['statute_of_limitations']=={'main':'exclude','first':'include','third':'include'}
    rows={r['id']:r for r in current.page()['rows']}
    assert rows['first']['edit_index']==rows['third']['edit_index']
    assert not rows['main']['checked'] and not rows['second']['checked']
    assert rows['second']['status']=='Not offered on this path'
    assert set(rows)==set(BOX_LABELS)
    assert review(history+answers((SUMMARY,'continue'))).current=='ambiguity_decision'


def test_debt_buyer_skips_timing_but_always_offers_the_main_choice():
    history=intake('buyer',oral='yes')
    assert review(history).current=='statute_of_limitations_decision'
    history+=answers(('statute_of_limitations_decision','no'))
    assert review(history).current=='sol_checkboxes_first_third'
    history+=answers(('sol_checkboxes_first_third','yes'))
    assert review(history).current=='sol_checkbox_second'
    history+=answers(('sol_checkbox_second','no'))
    current=review(history)
    assert current.current==SUMMARY
    assert 'sol_payment_estimate_agree' not in current.session.defense_answers
    assert current.session.checkbox_selections['statute_of_limitations']['main']=='exclude'
    assert not next(row for row in current.page()['rows'] if row['id']=='main')['checked']


@pytest.mark.parametrize('timing', ['yes','no','unknown'])
def test_missing_payment_uses_timing_question_without_inventing_date(timing):
    history=intake(payment='missing')
    assert review(history).current=='sol_payment_age'
    current=review(history+answers(('sol_payment_age',timing)))
    assert current.session.last_payment_complaint is None
    assert current.current==(SUMMARY if timing=='no' else 'statute_of_limitations_decision')
    if timing=='no':assert not current.session.checkbox_selections


def test_recent_payment_finishes_with_summary_and_no_checkbox_offer():
    history=intake(payment='2026-07-01')+answers(('sol_payment_estimate_agree','yes'))
    page=review(history).page()
    assert page['node_id']==SUMMARY
    assert all(not row['checked'] and row['edit_index'] is None for row in page['rows'])
    assert 'less than one year' in page['body'][0]


def test_back_and_changed_timing_clear_downstream_choices():
    prefix=intake()+answers(('sol_payment_estimate_agree','yes'))
    old=prefix+answers(('statute_of_limitations_decision','yes'),('sol_checkboxes_first_third','yes'))
    assert review(old).page()['node_id']==SUMMARY
    changed=intake(payment='2026-07-01')+answers(('sol_payment_estimate_agree','yes'))
    current=review(changed)
    assert current.current==SUMMARY
    assert not current.session.checkbox_selections
    # A client cannot append the now-stale defense choice to the changed path.
    with pytest.raises(ValueError,match='no longer match'):
        review(changed+answers(('statute_of_limitations_decision','yes')))
    # Merely going back renders the pending choice, with no later boxes recorded.
    back=review(prefix)
    assert back.current=='statute_of_limitations_decision'
    assert not back.session.checkbox_selections


def test_uncertainty_keeps_both_boxes_unselected_until_resolved():
    history=intake('buyer')+answers(('statute_of_limitations_decision','no'),('sol_checkboxes_first_third','unknown'))
    current=review(history)
    assert current.current=='sol_checkboxes_first_third_unresolved_help'
    assert current.session.defense_open_questions
    assert current.session.checkbox_selections['statute_of_limitations']=={'main':'exclude'}
    history+=answers((current.current,'retry'),('sol_checkboxes_first_third','no'))
    current=review(history)
    assert current.current==SUMMARY
    assert not current.session.defense_open_questions
    assert current.session.checkbox_selections['statute_of_limitations']=={'main':'exclude','first':'exclude','third':'exclude'}


def test_unknown_oral_answer_cannot_complete_until_it_is_resolved():
    history=intake('buyer',oral='unknown')+answers(('statute_of_limitations_decision','yes'),('sol_checkboxes_first_third','yes'))
    assert review(history).current=='guided_oral'
    history+=answers(('guided_oral','unknown'))
    assert review(history).current=='guided_oral'
    assert review(history+answers(('guided_oral','no'))).current==SUMMARY


@pytest.mark.parametrize('value',['2026-02-30','tomorrow','20260920','2026-9-2'])
def test_unusable_dates_do_not_advance(value):
    history = intake()
    index = next(i for i, a in enumerate(history) if a.node_id == 'guided_filing_date')
    prefix = history[:index]
    with pytest.raises(ValueError,match='date|YYYY'):
        review(prefix+answers(('guided_filing_date',value)))


def test_unknown_plaintiff_type_is_clarified_before_timing():
    history=intake('unknown')
    assert review(history).current=='guided_creditor_type'
    history+=answers(('guided_creditor_type','original'))
    assert review(history).current=='sol_payment_estimate_agree'


@pytest.mark.parametrize('node,value',[('guided_welcome','yes'),('guided_plaintiff',''),('sol_payment_estimate_agree','ambiguity_intro')])
def test_injected_or_out_of_order_answers_are_rejected(node,value):
    with pytest.raises(ValueError):
        review(answers((node,value)))


@pytest.fixture
def api():
    module=runpy.run_path(str(ROOT/'scripts/guided_clickthrough_demo.py'))
    return module,TestClient(module['create_app']({'PLAINTIFF':'Example Bank'}))


def test_api_uses_independent_request_state_and_serves_assets(api):
    _,client=api
    assert client.get('/').status_code==200
    assert client.get('/assets/app.js').status_code==200
    assert client.post('/api/state',json={'history':[]}).json()['node_id']=='guided_welcome'
    history=[a.model_dump() for a in intake('buyer')]
    assert client.post('/api/state',json={'history':history}).json()['node_id']=='statute_of_limitations_decision'
    assert client.post('/api/state',json={'history':[]}).json()['node_id']=='guided_welcome'
    response=client.post('/api/state',json={'history':[{'node_id':'sol_checkbox_second','value':'yes'}]})
    assert response.status_code==422


@pytest.mark.parametrize('intent', ['answer_node','ask_about_complaint','off_topic'])
def test_help_can_never_select_boxes_or_advance_even_if_model_returns_a_branch(api,intent):
    module,client=api
    captured=[]
    def model(**kwargs):
        captured.append(kwargs)
        return ChatTurnResponse(user_intent=intent,assistant_reply='An explanation.',next_node_id='yes',answer_confidence_pct=100)
    module['create_app'].__globals__['submit_chat_turn']=model
    history=[a.model_dump() for a in intake('buyer')+answers(('statute_of_limitations_decision','yes'))]
    before=client.post('/api/state',json={'history':history}).json()
    response=client.post('/api/help',json={'history':history,'question':'What do these boxes mean?','conversation':[]})
    assert response.status_code==200
    assert response.json()['next_node_id'] is None
    assert response.json()['user_intent']!='answer_node'
    after=client.post('/api/state',json={'history':history}).json()
    assert before==after
    assert captured[0]['payload']['current_node']['branches']==[]
    assert 'first and third' in captured[0]['payload']['current_node']['question']
    assert (ROOT/'prompts/guided_sol_clarification_system.md').read_text()==captured[0]['system']


def test_chat_provider_errors_are_safe_and_do_not_erase_answers(api):
    module,client=api
    def fail(**kwargs):raise RuntimeError('secret-provider-details')
    module['create_app'].__globals__['submit_chat_turn']=fail
    history=[a.model_dump() for a in intake('buyer')]
    response=client.post('/api/help',json={'history':history,'question':'What does this mean?'})
    assert response.status_code==503 and 'secret-provider-details' not in response.text
    assert client.post('/api/state',json={'history':history}).json()['node_id']=='statute_of_limitations_decision'


def completed_history(creditor='original', payment='2024-03-15', filing='2026-09-20', oral='no'):
    history = intake(creditor, payment, filing, oral)
    if creditor == 'original':
        history += answers(('sol_payment_estimate_agree', 'yes'))
    history += answers(('statute_of_limitations_decision', 'yes'), ('sol_checkboxes_first_third', 'yes'))
    if oral == 'yes':
        history += answers(('sol_checkbox_second', 'yes'))
    assert review(history).current == SUMMARY
    return history


def change(history, node, value, revision=None):
    from advocate_bot_qualtrics.practice_areas.consumer_debt.guided_sol import GuidedEditRequest, edit_review
    index = next(i for i, answer in enumerate(history) if answer.node_id == node)
    return edit_review({}, GuidedEditRequest(history=history, edit_index=index, value=value, revision=revision))


def advance_updated(current, value):
    from advocate_bot_qualtrics.practice_areas.consumer_debt.guided_sol import GuidedAdvanceRequest, advance_review
    return advance_review({}, GuidedAdvanceRequest(history=current.history, revision=current.revision, value=value))


def test_name_edit_returns_to_summary_and_preserves_all_other_fields_and_choices():
    current = change(completed_history(), 'guided_plaintiff', 'Corrected Bank')
    assert current.current == SUMMARY
    assert current.session.plaintiff_name == 'Corrected Bank'
    assert current.session.filing_date == date(2026, 9, 20)
    assert current.session.last_payment_complaint == date(2024, 3, 15)
    assert current.session.preliminary_fields['ORAL'].value == 'no'
    assert current.session.checkbox_selections[DEFENSE_KEY] == {'main': 'include', 'first': 'include', 'third': 'include'}
    assert current.page()['changes'] == []
    assert 'unchanged' in current.page()['revision_notice']


DEFENSE_KEY = 'statute_of_limitations'


@pytest.mark.parametrize('payment', ['2024-09-20', '2025-09-20'])
def test_payment_edit_with_same_year_screen_skips_questions_without_fabricating_date_agreement(payment):
    current = change(completed_history(), 'guided_payment_date', payment)
    assert current.current == SUMMARY
    assert len(current.session.checkbox_selections[DEFENSE_KEY]) == 3
    assert current.page()['changes'] == []
    assert 'sol_payment_estimate_agree' not in current.session.defense_answers
    retained = next(a for a in current.history if a.node_id == 'sol_payment_estimate_agree')
    assert retained.value == 'reuse_comparison' and retained.automatic
    assert retained.timing_basis.kind == 'comparison'
    assert review(current.history).page()['rows'] == current.page()['rows']


def test_filing_date_edit_can_remove_boxes_without_repeating_unrelated_fields():
    current = change(completed_history(), 'guided_filing_date', '2024-08-01')
    assert current.current == SUMMARY
    assert not current.session.checkbox_selections
    assert current.session.preliminary_fields['ORAL'].value == 'no'
    assert len(current.page()['changes']) == 3
    assert all(change['after'] == 'Not offered on this path' for change in current.page()['changes'])
    assert 'less than one year' in current.page()['body'][0]


def test_payment_edit_across_year_boundary_asks_only_necessary_date_review():
    current = change(completed_history(), 'guided_payment_date', '2026-07-01')
    assert current.current == 'sol_payment_estimate_agree'
    assert current.session.filing_date == date(2026, 9, 20)
    assert current.session.preliminary_fields['ORAL'].value == 'no'
    current = advance_updated(current, 'yes')
    assert current.current == SUMMARY
    assert not current.session.checkbox_selections
    assert {item['before'] for item in current.page()['changes']} == {'Selected'}


def test_declining_changed_payment_date_retains_valid_choices_after_timing_is_resolved():
    current = change(completed_history(), 'guided_payment_date', '2026-07-01')
    current = advance_updated(current, 'no')
    assert current.current == 'sol_payment_age'
    current = advance_updated(current, 'yes')
    assert current.current == SUMMARY
    assert len(current.session.checkbox_selections[DEFENSE_KEY]) == 3
    assert current.page()['changes'] == []


def test_written_to_oral_edit_asks_only_new_second_box():
    current = change(completed_history(), 'guided_oral', 'yes')
    assert current.current == 'sol_checkbox_second'
    assert current.session.checkbox_selections[DEFENSE_KEY] == {'main': 'include', 'first': 'include', 'third': 'include'}
    current = advance_updated(current, 'no')
    assert current.current == SUMMARY
    assert current.session.checkbox_selections[DEFENSE_KEY]['second'] == 'exclude'
    assert current.page()['changes'] == [{'label': 'California · oral contract', 'before': 'Not offered on this path', 'after': 'Not selected'}]


def test_oral_to_written_removes_only_second_box():
    current = change(completed_history(oral='yes'), 'guided_oral', 'no')
    assert current.current == SUMMARY
    assert current.session.checkbox_selections[DEFENSE_KEY] == {'main': 'include', 'first': 'include', 'third': 'include'}
    assert len(current.page()['changes']) == 1
    assert current.page()['changes'][0]['label'] == 'California · oral contract'


def test_original_to_buyer_keeps_all_choices_without_requesting_a_name():
    current = change(completed_history(oral='yes'), 'guided_creditor_type', 'buyer')
    assert current.current == SUMMARY
    assert current.session.checkbox_selections[DEFENSE_KEY] == {'main': 'include', 'first': 'include', 'third': 'include', 'second': 'include'}
    assert current.session.original_creditor is None
    assert next(a for a in current.history if a.node_id == 'guided_original_creditor').automatic
    assert current.page()['changes'] == []


def test_buyer_to_original_asks_timing_and_keeps_all_still_eligible_choices():
    current = change(completed_history('buyer', oral='yes'), 'guided_creditor_type', 'original')
    assert current.current == 'sol_payment_estimate_agree'
    current = advance_updated(current, 'yes')
    assert current.current == SUMMARY
    assert current.session.checkbox_selections[DEFENSE_KEY] == {'main': 'include', 'first': 'include', 'third': 'include', 'second': 'include'}


def test_an_existing_personal_estimate_is_retained_when_filing_date_does_not_change():
    history = intake(payment='missing') + answers(('sol_payment_age', 'yes'), ('statute_of_limitations_decision', 'yes'), ('sol_checkboxes_first_third', 'yes'))
    current = change(history, 'guided_payment_date', '2026-07-01')
    assert current.current == SUMMARY
    assert current.session.defense_answers['sol_payment_age'] == 'yes'
    assert 'sol_payment_estimate_agree' not in current.session.defense_answers
    assert current.page()['changes'] == []


def test_changed_filing_date_invalidates_a_personal_estimate_but_not_other_facts():
    history = intake(payment='missing') + answers(('sol_payment_age', 'yes'), ('statute_of_limitations_decision', 'yes'), ('sol_checkboxes_first_third', 'yes'))
    current = change(history, 'guided_filing_date', '2025-09-20')
    assert current.current == 'sol_payment_age'
    assert current.session.preliminary_fields['ORAL'].value == 'no'
    current = advance_updated(current, 'yes')
    assert current.current == SUMMARY and current.page()['changes'] == []


def test_removed_choices_do_not_reappear_automatically_on_a_later_edit():
    current = change(completed_history(), 'guided_payment_date', '2026-07-01')
    current = advance_updated(current, 'yes')
    assert current.current == SUMMARY and not current.session.checkbox_selections
    current = change(current.history, 'guided_payment_date', '2024-03-15', revision=current.revision)
    assert current.current == 'sol_payment_estimate_agree'
    current = advance_updated(current, 'yes')
    assert current.current == 'statute_of_limitations_decision'
    assert not current.session.checkbox_selections


def test_another_edit_during_targeted_review_keeps_valid_saved_answers():
    current = change(completed_history(), 'guided_oral', 'yes')
    current = change(current.history, 'guided_plaintiff', 'Corrected Bank', revision=current.revision)
    assert current.current == 'sol_checkbox_second'
    current = advance_updated(current, 'yes')
    assert current.current == SUMMARY
    assert len(current.session.checkbox_selections[DEFENSE_KEY]) == 4


def test_explicit_uncertainty_replaces_an_old_choice_instead_of_restoring_it():
    current = change(completed_history(), 'statute_of_limitations_decision', 'unknown')
    assert current.current == 'statute_of_limitations_decision_unresolved_help'
    current = advance_updated(current, 'retry')
    assert current.current == 'statute_of_limitations_decision'
    assert 'main' not in current.session.checkbox_selections.get(DEFENSE_KEY, {})
    current = advance_updated(current, 'no')
    assert current.current == SUMMARY
    assert current.session.checkbox_selections[DEFENSE_KEY]['main'] == 'exclude'


def test_timing_reuse_cannot_cross_a_changed_screening_boundary():
    from advocate_bot_qualtrics.practice_areas.consumer_debt.guided_sol import TimingBasis
    history = intake(payment='2026-07-01')
    history += [GuidedAnswer(node_id='sol_payment_estimate_agree', value='reuse_comparison', automatic=True,
                            timing_basis=TimingBasis(kind='comparison', payment_date=date(2024, 3, 15), filing_date=date(2026, 9, 20)))]
    with pytest.raises(ValueError, match='new timing review'):
        review(history)


def test_edit_api_round_trips_retained_answers_and_summary_changes(api):
    _, client = api
    history = completed_history()
    request = {'history': [a.model_dump(mode='json') for a in history], 'edit_index': next(i for i, a in enumerate(history) if a.node_id == 'sol_payment_estimate_agree'), 'value': 'yes'}
    result = client.post('/api/edit', json=request)
    assert result.status_code == 200
    # Changing the date agreement to its existing answer still
    # skips the subsequent questions and returns the saved summary.
    payload = result.json()
    assert payload['page']['node_id'] == SUMMARY
    assert payload['page']['changes'] == []
    assert client.post('/api/state', json={'history': payload['history'], 'revision': payload['revision']}).json() == payload['page']
    payload = client.post('/api/advance', json={'history': payload['history'], 'revision': payload['revision'], 'value': 'continue'}).json()
    assert payload['page']['node_id'] == 'ambiguity_decision'


def both_defenses_history(sol_history=None, ambiguity='yes', complete=True):
    history = (completed_history() if sol_history is None else sol_history) + answers((SUMMARY, 'continue'), ('ambiguity_decision', ambiguity))
    assert review(history).current == AMBIGUITY_SUMMARY
    return remaining_defenses(history) if complete else history


def remaining_defenses(history):
    return history + answers((AMBIGUITY_SUMMARY, 'continue'), (IDENTITY_INTRO, 'continue'),
        (IDENTITY_SUMMARY, 'continue'), (LACHES_INTRO, 'continue'), ('laches', 'no'),
        ('laches_statements', 'no'), ('laches_lost_info', 'no'), (LACHES_SUMMARY, 'continue'))


def finish_retained_sections(current):
    for _ in range(8):
        if current.current == COMPLETE:
            return current
        assert current.current in {IDENTITY_SUMMARY, LACHES_SUMMARY}
        current = advance_updated(current, 'continue')
    raise AssertionError('Retained sections did not finish')


@pytest.mark.parametrize('creditor', ['buyer', 'original'])
@pytest.mark.parametrize('oral', ['yes', 'no'])
@pytest.mark.parametrize('main,group,ambiguity', [('no', 'yes', 'no'), ('yes', 'no', 'yes'), ('no', 'no', 'no')])
def test_two_defenses_have_independent_choices_and_per_defense_summaries(creditor, oral, main, group, ambiguity):
    history = intake(creditor, oral=oral)
    if creditor == 'original':
        history += answers(('sol_payment_estimate_agree', 'yes'))
    history += answers(('statute_of_limitations_decision', main), ('sol_checkboxes_first_third', group))
    if oral == 'yes':
        history += answers(('sol_checkbox_second', 'no'))
    sol = review(history)
    assert sol.page()['section_number'] == 2
    assert sol.page()['next_label'] == 'Continue to Ambiguity'
    history += answers((SUMMARY, 'continue'))
    current = review(history)
    assert current.current == 'ambiguity_decision'
    page = current.page()
    assert page['section'] == 'Ambiguity' and page['section_number'] == 3
    assert any('entire account history or contract' in text for text in page['body'])
    assert 'visual' not in page
    assert current.session.defense_results[DEFENSE_KEY]['status'] == 'confirmed'
    history += answers(('ambiguity_decision', ambiguity))
    current = review(history)
    assert current.current == AMBIGUITY_SUMMARY
    page = current.page()
    assert len(page['rows']) == 1
    assert page['rows'][0]['checked'] == (ambiguity == 'yes')
    assert 'don’t want to check off' in page['body'][0] if ambiguity == 'no' else 'you’d like to check off' in page['body'][0]
    # "main" identifies different boxes in the two defenses; Change must point
    # to each defense's own question.
    assert history[page['rows'][0]['edit_index']].node_id == 'ambiguity_decision'
    assert review(history + answers((AMBIGUITY_SUMMARY, 'continue'))).current == IDENTITY_INTRO
    current = review(remaining_defenses(history))
    assert current.current == COMPLETE
    final = current.page()
    assert [g['section'] for g in final['groups']] == ['Statute of Limitations', 'Ambiguity', 'Identity Theft', 'Laches']
    assert len(final['rows']) == 7
    assert all(row['detail'] == 'Main checkbox' for row in final['rows'] if row['id'] == 'main')
    assert current.session.defense_results['ambiguity']['status'] == 'confirmed'
    assert all(TREE.node(n).discussion_topic in {'Statute of Limitations', 'Ambiguity', 'Identity Theft', 'Laches'} for n in current.session.script_visited)


def test_recent_sol_finish_still_offers_ambiguity_without_inventing_sol_confirmation():
    history = intake(payment='2026-07-01') + answers(('sol_payment_estimate_agree', 'yes'))
    current = review(history)
    assert current.current == SUMMARY
    assert 'does not apply' in current.page()['body'][0]
    assert current.session.defense_results[DEFENSE_KEY]['status'] == 'finished'
    history += answers((SUMMARY, 'continue'))
    assert review(history).current == 'ambiguity_decision'
    assert review(history).session.defense_results[DEFENSE_KEY]['status'] == 'finished'
    current = review(both_defenses_history(history[:-1], ambiguity='yes'))
    assert current.session.checkbox_selections == {'ambiguity': {'main': 'include'}}


def test_ambiguity_uncertainty_blocks_completion_until_explicitly_resolved():
    history = completed_history() + answers((SUMMARY, 'continue'), ('ambiguity_decision', 'unknown'))
    current = review(history)
    assert current.current == 'ambiguity_decision_unresolved_help'
    assert current.session.defense_open_questions
    assert 'ambiguity' not in current.session.checkbox_selections
    with pytest.raises(ValueError, match='no longer match'):
        review(history + answers((AMBIGUITY_SUMMARY, 'continue')))
    history += answers(('ambiguity_decision_unresolved_help', 'retry'), ('ambiguity_decision', 'no'))
    current = review(history)
    assert current.current == AMBIGUITY_SUMMARY
    assert not current.session.defense_open_questions
    assert current.page()['rows'][0]['status'] == 'Not selected'


def test_editing_ambiguity_preserves_sol_and_reports_only_the_ambiguity_change():
    history = both_defenses_history()
    current = change(history, 'ambiguity_decision', 'no')
    assert current.current == AMBIGUITY_SUMMARY
    assert current.page()['changes'] == [{'label': 'Ambiguity', 'before': 'Selected', 'after': 'Not selected'}]
    assert current.session.checkbox_selections[DEFENSE_KEY] == review(history).session.checkbox_selections[DEFENSE_KEY]
    current = finish_retained_sections(advance_updated(current, 'continue'))
    assert current.current == COMPLETE
    assert current.page()['groups'][1]['rows'][0]['previous_status'] == 'Selected'


def test_sol_edit_retains_later_ambiguity_choice_without_reasking_it():
    current = change(both_defenses_history(), 'guided_payment_date', '2026-07-01')
    assert current.current == 'sol_payment_estimate_agree'
    current = advance_updated(current, 'yes')
    assert current.current == SUMMARY
    assert not current.session.checkbox_selections
    current = advance_updated(current, 'continue')
    assert current.current == AMBIGUITY_SUMMARY
    assert current.session.checkbox_selections == {'ambiguity': {'main': 'include'}}
    assert current.page()['changes'] == []
    current = finish_retained_sections(advance_updated(current, 'continue'))
    assert current.current == COMPLETE


def test_two_edits_at_sol_summary_do_not_erase_saved_ambiguity_choice():
    current = change(both_defenses_history(), 'guided_plaintiff', 'Renamed Bank')
    assert current.current == SUMMARY
    current = change(current.history, 'guided_plaintiff', 'Another Bank', current.revision)
    current = advance_updated(current, 'continue')
    assert current.current == AMBIGUITY_SUMMARY
    assert current.session.checkbox_selections['ambiguity']['main'] == 'include'


def test_ambiguity_chat_receives_current_script_and_never_advances(api):
    module, client = api
    captured = []
    def model(**kwargs):
        captured.append(kwargs)
        return ChatTurnResponse(user_intent='off_topic', assistant_reply='Ignored', next_node_id=None)
    module['create_app'].__globals__['submit_chat_turn'] = model
    history = [a.model_dump(mode='json') for a in completed_history() + answers((SUMMARY, 'continue'))]
    response = client.post('/api/help', json={'history': history, 'question': 'What does ambiguity mean?'})
    assert response.status_code == 200
    assert response.json()['next_node_id'] is None
    assert 'Ambiguity' in response.json()['assistant_reply']
    context = captured[0]['payload']['current_node']
    assert context['discussion_topic'] == 'Ambiguity'
    assert 'entire account history or contract' in context['explanation']['text']
    assert client.post('/api/state', json={'history': history}).json()['node_id'] == 'ambiguity_decision'


def test_october_30_wording_matches_source_and_does_not_change_chatbot_copy():
    import re
    from zipfile import ZipFile
    from xml.etree import ElementTree as ET
    from advocate_bot_qualtrics.practice_areas.consumer_debt.guided_sol import CONTENT
    with ZipFile(ROOT / CONTENT['source']) as document:
        root = ET.fromstring(document.read('word/document.xml'))
    namespace = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    source = ' '.join(''.join(p.itertext()) for p in root.findall('.//w:p', namespace))
    normalize = lambda text: re.sub(r'\s+', ' ', text).strip()
    for overrides in CONTENT['nodes'].values():
        for text in overrides.values():
            assert normalize(text) in normalize(source)
    for text in CONTENT['confirmation'].values():
        assert normalize(text) in normalize(source)
    assert 'strong defense' in review(intake()[:-1]).page()['body'][0]
    assert 'strong defense' not in TREE.node('statute_of_limitations_intro').explanation.text
    buyer = review(intake('buyer')).page()
    assert any('Debt buyers often sue on older accounts' in text for text in buyer['body'])
    assert 'even if their last payment' not in buyer['help_text']


def test_invalid_edit_indexes_and_non_question_pages_are_rejected(api):
    _, client = api
    history = [a.model_dump(mode='json') for a in completed_history()]
    assert client.post('/api/edit', json={'history': history, 'edit_index': 79, 'value': 'yes'}).status_code == 422
    assert client.post('/api/edit', json={'history': history, 'edit_index': 0, 'value': 'continue'}).status_code == 422


@pytest.mark.parametrize('payment,filing', [('2026-09-19','2026-09-20'),('missing','unknown')])
def test_buyer_date_edits_have_no_effect_on_offers_or_saved_choices(payment, filing):
    current = change(completed_history('buyer'), 'guided_payment_date', payment)
    assert current.current == SUMMARY
    current = change(current.history, 'guided_filing_date', filing, revision=current.revision)
    assert current.current == SUMMARY
    assert current.revision.plan.required_questions == []
    assert current.page()['changes'] == []
    assert current.session.checkbox_selections[DEFENSE_KEY] == {'main': 'include', 'first': 'include', 'third': 'include'}


def test_name_changes_are_personalization_even_when_the_name_is_completely_different():
    current = change(completed_history('buyer'), 'guided_original_creditor', 'A Different Name')
    assert current.current == SUMMARY
    assert current.revision.plan.affected_boxes == []
    assert current.revision.plan.required_questions == []
    assert current.page()['changes'] == []


def test_backward_plan_identifies_only_the_new_oral_checkbox_question():
    current = change(completed_history(), 'guided_oral', 'yes')
    assert current.revision.plan.affected_boxes == ['second']
    assert current.revision.plan.required_questions == ['sol_checkbox_second']
    assert current.current == 'sol_checkbox_second'


def test_recent_original_to_buyer_offers_main_without_repeating_timing():
    history = intake(payment='2026-07-01') + answers(('sol_payment_estimate_agree','yes'))
    current = change(history, 'guided_creditor_type', 'buyer')
    assert current.current == 'statute_of_limitations_decision'
    assert current.revision.plan.required_questions == ['statute_of_limitations_decision', 'sol_checkboxes_first_third']
    current = advance_updated(current, 'no')
    assert current.current == 'sol_checkboxes_first_third'
    current = advance_updated(current, 'yes')
    assert current.current == SUMMARY
    assert current.session.checkbox_selections[DEFENSE_KEY] == {'main': 'exclude', 'first': 'include', 'third': 'include'}


def test_switching_back_to_original_reuses_still_valid_timing_facts():
    current = change(completed_history(), 'guided_creditor_type', 'buyer')
    assert current.current == SUMMARY
    current = change(current.history, 'guided_creditor_type', 'original', revision=current.revision)
    assert current.current == SUMMARY
    assert current.revision.plan.required_questions == []
    assert current.page()['changes'] == []
    assert current.session.checkbox_selections[DEFENSE_KEY] == {'main': 'include', 'first': 'include', 'third': 'include'}


def identity_history(recognize='yes'):
    history = both_defenses_history(complete=False)
    history = [a.model_copy(update={'value': recognize}) if a.node_id == 'guided_recognize' else a for a in history]
    history += answers((AMBIGUITY_SUMMARY, 'continue'))
    assert review(history).current == IDENTITY_INTRO
    return history


def laches_history():
    history = identity_history() + answers((IDENTITY_INTRO, 'continue'), (IDENTITY_SUMMARY, 'continue'))
    assert review(history).current == LACHES_INTRO
    return history + answers((LACHES_INTRO, 'continue'))


def continue_retained_to(current, node):
    for _ in range(8):
        if current.current == node:
            return current
        assert current.current in {SUMMARY, AMBIGUITY_SUMMARY, IDENTITY_SUMMARY, LACHES_SUMMARY}
        current = advance_updated(current, 'continue')
    raise AssertionError(f'Did not reach {node}')


def test_recognized_account_finishes_identity_without_a_checkbox_offer_or_repeating_intake():
    history = identity_history()
    page = review(history).page()
    assert page['section'] == 'Identity Theft' and page['section_number'] == 4
    assert 'without your permission' in page['body'][0]
    current = review(history + answers((IDENTITY_INTRO, 'continue')))
    assert current.current == IDENTITY_SUMMARY
    assert 'recognize the account' in current.page()['body'][0]
    assert current.page()['rows'][0]['status'] == 'Not offered on this path'
    assert current.page()['rows'][0]['detail'] == 'Main checkbox'
    assert review_nodes(current) == ['guided_recognize']
    assert 'identity_suspected' not in current.session.defense_answers
    assert 'identity_theft' not in current.session.checkbox_selections
    assert not current.session.defense_open_questions


def test_unknown_recognition_returns_to_preliminary_section_then_resumes_identity():
    history = identity_history('unknown') + answers((IDENTITY_INTRO, 'continue'))
    current = review(history)
    assert current.current == 'guided_recognize'
    assert current.page()['section'] == 'Preliminary fields'
    current = advance_updated(current, 'unknown')
    assert current.current == 'guided_recognize'
    current = advance_updated(current, 'no')
    assert current.current == 'identity_suspected'
    assert current.page()['section'] == 'Identity Theft'
    assert current.session.preliminary_fields['RECOGNIZE'].value == 'no'


def test_unsuspected_identity_theft_finishes_without_offering_a_checkbox():
    history = identity_history('no') + answers((IDENTITY_INTRO, 'continue'), ('identity_suspected', 'no'))
    current = review(history)
    assert current.current == IDENTITY_SUMMARY
    assert 'does not apply' in current.page()['body'][0]
    assert review_nodes(current) == ['guided_recognize', 'identity_suspected']
    assert current.session.defense_results['identity_theft']['status'] == 'finished'
    assert 'identity_theft' not in current.session.checkbox_selections


def test_identity_referral_requires_staff_resolution_and_never_selects_a_checkbox():
    history = identity_history('no') + answers((IDENTITY_INTRO, 'continue'), ('identity_suspected', 'yes'))
    current = review(history)
    assert current.current == 'identity_referral_help'
    assert current.session.defense_open_questions
    assert 'file a report' in ' '.join(current.page()['body'])
    with pytest.raises(ValueError, match='Choose one'):
        review(history + answers(('identity_referral_help', 'continue')))
    with pytest.raises(ValueError, match='no longer match'):
        review(history + answers((IDENTITY_SUMMARY, 'continue')))
    history += answers(('identity_referral_help', 'unknown'))
    assert review(history).current == 'identity_referral_help'
    history += answers(('identity_referral_help', 'resolved'))
    current = review(history)
    assert current.current == IDENTITY_SUMMARY
    assert current.session.defense_results['identity_theft']['status'] == 'referred'
    assert not current.session.defense_open_questions
    assert 'identity_theft' not in current.session.checkbox_selections
    assert 'has not selected' in current.page()['body'][0]
    assert not current.page()['rows'][0]['checked']


def test_identity_uncertainty_does_not_mean_no_and_cannot_finish_until_resolved():
    history = identity_history('no') + answers((IDENTITY_INTRO, 'continue'), ('identity_suspected', 'unknown'))
    current = review(history)
    assert current.current == 'identity_uncertain_help'
    assert current.session.defense_open_questions
    history += answers(('identity_uncertain_help', 'retry'), ('identity_suspected', 'no'))
    current = review(history)
    assert current.current == IDENTITY_SUMMARY
    assert not current.session.defense_open_questions


@pytest.mark.parametrize('values', __import__('itertools').product(['yes', 'no', 'unknown'], repeat=3))
def test_laches_any_yes_all_no_and_uncertainty_paths(values):
    history = laches_history()
    assert 'lost or become unavailable' in review(history).page()['help_text']
    for node, value in zip(['laches', 'laches_statements', 'laches_lost_info'], values):
        assert review(history).current == node
        history += answers((node, value))
    current = review(history)
    if 'yes' in values:
        assert current.current == 'laches_decision'
        assert not current.session.defense_open_questions
        assert 'visual' not in current.page()
        for choice in ['yes', 'no']:
            decided = review(history + answers(('laches_decision', choice)))
            assert decided.current == LACHES_SUMMARY
            assert decided.page()['rows'][0]['checked'] == (choice == 'yes')
            assert len(decided.page()['review_answers']) == 1
            assert decided.page()['review_answers'][0]['value'] == 'Yes'
    elif 'unknown' in values:
        pending = ['laches_unresolved_help', 'laches_statements_unresolved_help', 'laches_lost_info_unresolved_help'][values.index('unknown')]
        assert current.current == pending
        assert current.session.defense_open_questions
        assert 'laches' not in current.session.checkbox_selections
    else:
        assert current.current == LACHES_SUMMARY
        assert current.session.defense_results['laches']['status'] == 'finished'
        assert all(row['value'] == 'No' for row in current.page()['review_answers'])
        assert len(current.page()['review_answers']) == 3
        assert 'laches' not in current.session.checkbox_selections


def test_laches_clarifies_only_the_unresolved_fact_and_then_requires_a_choice():
    history = laches_history() + answers(('laches', 'no'), ('laches_statements', 'unknown'), ('laches_lost_info', 'no'))
    assert review(history).current == 'laches_statements_unresolved_help'
    history += answers(('laches_statements_unresolved_help', 'retry'))
    assert review(history).current == 'laches_statements_resolve'
    history += answers(('laches_statements_resolve', 'yes'))
    assert review(history).current == 'laches_decision'
    history += answers(('laches_decision', 'unknown'))
    assert review(history).current == 'laches_decision_unresolved_help'
    history += answers(('laches_decision_unresolved_help', 'retry'), ('laches_decision', 'no'))
    current = review(history)
    assert current.current == LACHES_SUMMARY
    assert not current.session.defense_open_questions
    assert review_nodes(current) == ['laches_statements_resolve']


def test_laches_choice_edit_changes_only_laches_and_keeps_other_defenses():
    history = laches_history() + answers(('laches', 'yes'), ('laches_statements', 'no'), ('laches_lost_info', 'no'),
                                        ('laches_decision', 'yes'), (LACHES_SUMMARY, 'continue'))
    current = change(history, 'laches_decision', 'no')
    assert current.current == LACHES_SUMMARY
    assert current.page()['changes'] == [{'label': 'Laches', 'before': 'Selected', 'after': 'Not selected'}]
    assert current.session.checkbox_selections[DEFENSE_KEY] == review(history).session.checkbox_selections[DEFENSE_KEY]
    assert advance_updated(current, 'continue').current == COMPLETE


def test_laches_removed_choice_is_not_restored_after_another_completed_edit():
    history = laches_history() + answers(('laches', 'yes'), ('laches_statements', 'no'), ('laches_lost_info', 'no'),
                                        ('laches_decision', 'yes'), (LACHES_SUMMARY, 'continue'))
    current = change(history, 'laches', 'no')
    assert current.current == LACHES_SUMMARY
    assert 'laches' not in current.session.checkbox_selections
    current = advance_updated(current, 'continue')
    current = change(current.history, 'laches', 'yes', current.revision)
    assert current.current == 'laches_decision'
    assert 'laches' not in current.session.checkbox_selections


def test_new_identity_followup_preserves_laches_and_requires_staff_before_advancing():
    history = laches_history() + answers(('laches', 'no'), ('laches_statements', 'yes'), ('laches_lost_info', 'no'),
                                        ('laches_decision', 'yes'), (LACHES_SUMMARY, 'continue'))
    current = change(history, 'guided_recognize', 'no')
    current = continue_retained_to(current, 'identity_suspected')
    current = advance_updated(current, 'yes')
    assert current.current == 'identity_referral_help'
    current = advance_updated(current, 'resolved')
    assert current.current == IDENTITY_SUMMARY
    current = advance_updated(current, 'continue')
    assert current.current == LACHES_SUMMARY
    assert current.session.checkbox_selections['laches']['main'] == 'include'
    assert 'identity_theft' not in current.session.checkbox_selections


def test_unrelated_edit_reuses_staff_resolution_but_changed_recognition_invalidates_it():
    history = identity_history('no') + answers((IDENTITY_INTRO, 'continue'), ('identity_suspected', 'yes'),
        ('identity_referral_help', 'resolved'), (IDENTITY_SUMMARY, 'continue'), (LACHES_INTRO, 'continue'),
        ('laches', 'no'), ('laches_statements', 'no'), ('laches_lost_info', 'no'), (LACHES_SUMMARY, 'continue'))
    current = change(history, 'guided_plaintiff', 'Corrected Name')
    current = continue_retained_to(current, IDENTITY_SUMMARY)
    assert not current.session.defense_open_questions
    assert any(a.node_id == 'identity_referral_help' and a.automatic for a in current.history)
    current = change(history, 'guided_recognize', 'yes')
    current = finish_retained_sections(continue_retained_to(current, IDENTITY_SUMMARY))
    current = change(current.history, 'guided_recognize', 'no', current.revision)
    current = continue_retained_to(current, 'identity_referral_help')
    assert current.session.defense_open_questions


def test_two_preliminary_edits_preserve_future_laches_choice():
    history = laches_history() + answers(('laches', 'yes'), ('laches_statements', 'no'), ('laches_lost_info', 'no'),
                                        ('laches_decision', 'yes'), (LACHES_SUMMARY, 'continue'))
    current = change(history, 'guided_plaintiff', 'First Name')
    current = change(current.history, 'guided_amount', '900.00', current.revision)
    current = finish_retained_sections(continue_retained_to(current, IDENTITY_SUMMARY))
    assert current.current == COMPLETE
    assert current.session.checkbox_selections['laches']['main'] == 'include'


@pytest.mark.parametrize('topic,node,history', [
    ('Identity Theft', 'identity_suspected', identity_history('no') + answers((IDENTITY_INTRO, 'continue'))),
    ('Laches', 'laches', laches_history()),
])
def test_new_defense_chat_uses_approved_context_and_cannot_advance(api, topic, node, history):
    module, client = api
    captured = []
    def model(**kwargs):
        captured.append(kwargs)
        return ChatTurnResponse(user_intent='answer_node', assistant_reply='Check it', next_node_id='yes')
    module['create_app'].__globals__['submit_chat_turn'] = model
    response = client.post('/api/help', json={'history': [a.model_dump(mode='json') for a in history], 'question': 'Please explain'})
    assert response.status_code == 200 and response.json()['next_node_id'] is None
    assert response.json()['user_intent'] != 'answer_node'
    assert captured[0]['payload']['current_node']['discussion_topic'] == topic
    assert client.post('/api/state', json={'history': [a.model_dump(mode='json') for a in history]}).json()['node_id'] == node


def test_unrelated_edit_retains_irrelevant_laches_unknowns_without_reasking():
    history = laches_history() + answers(('laches', 'unknown'), ('laches_statements', 'yes'), ('laches_lost_info', 'unknown'),
                                        ('laches_decision', 'yes'), (LACHES_SUMMARY, 'continue'))
    current = change(history, 'guided_plaintiff', 'Changed Name')
    current = finish_retained_sections(continue_retained_to(current, IDENTITY_SUMMARY))
    assert current.current == COMPLETE
    assert current.session.checkbox_selections['laches']['main'] == 'include'
    assert current.session.defense_answers['laches'] == 'unknown'
    assert not current.session.defense_open_questions


def test_laches_clarification_is_reused_after_an_unrelated_edit():
    history = laches_history() + answers(('laches', 'no'), ('laches_statements', 'unknown'), ('laches_lost_info', 'no'),
        ('laches_statements_unresolved_help', 'retry'), ('laches_statements_resolve', 'yes'),
        ('laches_decision', 'yes'), (LACHES_SUMMARY, 'continue'))
    current = change(history, 'guided_plaintiff', 'Corrected Name')
    current = finish_retained_sections(continue_retained_to(current, IDENTITY_SUMMARY))
    assert current.current == COMPLETE
    assert current.session.defense_answers['laches_statements'] == 'yes'
    assert current.session.checkbox_selections['laches']['main'] == 'include'
    assert not current.session.defense_open_questions
