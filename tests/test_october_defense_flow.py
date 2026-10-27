"""Full October 25 engine traversals and complaint-presence routing."""
from itertools import product
import pytest

from advocate_bot_qualtrics.practice_areas.consumer_debt.affirmative_defenses import DOCUMENTED_DEFENSES, script_condition
from advocate_bot_qualtrics.practice_areas.consumer_debt.session import apply_interactive_branch
from advocate_bot_qualtrics.practice_areas.consumer_debt.tree import INTERACTIVE_TREE_DEFINITION as TREE


@pytest.mark.parametrize('creditor,claim,recognition,oral,consolidation',list(product(['original','buyer'],['breach','common','both'],['yes','no'],['yes','no'],['yes','no'])))
def test_complete_engine_traversal_retains_choices_and_reaches_terminal(creditor,claim,recognition,oral,consolidation,scripted_engine):
    e=scripted_engine(**{'PLAINTIFF.TYPE':creditor,'SUIT.TYPE':claim,'OWNERSHIP':False,'OWNERSHIP.PROOF':False,'STATEMENT':False,'OPEN.DATE':None,'LAST.PAYMENT.DATE':None,'BREACH.DATE':None})
    for node,branch in [('prelim_recognize',recognition),('prelim_oral',oral),('prelim_consolidation',consolidation)]:apply_interactive_branch(e.session,node,branch)
    e._drain_hooks();visited=[]
    for _ in range(180):
        if e.tree_complete:break
        n=TREE.node(e.current_node_id);visited.append(n.id)
        branch='submit' if n.input else 'continue' if n.discussion_mode=='confirmation' else 'resolved' if n.discussion_mode=='referral' else 'yes'
        step=e.submit('Spanish' if n.input else branch)
        assert step.error is None,(n.id,step.error)
    else:pytest.fail('The traversal failed to complete within its bounded question count')
    assert e.current_node_id=='review_questions'
    assert set(e.session.defense_results)==set(DOCUMENTED_DEFENSES)
    assert not e.session.defense_open_questions
    assert len([n for n in e.session.script_visited if n.endswith('_intro')])==21
    assert 'Open questions / clinic review:' in e.transcript[-1][1]
    assert 'Your defense choices:' in e.transcript[-1][1]
    assert e.last_export_path
    if recognition=='no':
        assert 'identity_referral_help' in visited and 'wrong_party_referral_help' in visited
        assert 'fraud_hidden_facts' not in visited
    if claim=='both':
        assert 'cause_breach_main' in visited
        assert 'cause_common_main' not in visited  # It is the same main checkbox.
    assert 'capacity_incapacitated' not in visited


@pytest.mark.parametrize('payment_present,breach_present',list(product([True,False],repeat=2)))
def test_missing_date_box_requires_both_dates_absent(payment_present,breach_present,scripted_engine):
    e=scripted_engine('cause_breach_payment',**{'LAST.PAYMENT.DATE':'2024-01-01' if payment_present else None,'BREACH.DATE':'2024-02-01' if breach_present else None})
    e._drain_hooks()
    assert (e.current_node_id=='cause_breach_fourth_original')==(not payment_present and not breach_present)


@pytest.mark.parametrize('statement,proof',list(product([True,False],repeat=2)))
def test_attachment_checkbox_is_offered_only_when_both_attachments_absent(statement,proof,scripted_engine):
    e=scripted_engine('cause_breach_attachments',**{'PLAINTIFF.TYPE':'buyer','STATEMENT':statement,'OWNERSHIP.PROOF':proof})
    e._drain_hooks()
    assert (e.current_node_id=='cause_breach_attachment_checkbox')==(not statement and not proof)


def test_corrected_personal_date_does_not_erase_complaint_presence(scripted_engine):
    e=scripted_engine('cause_breach_payment')
    original=e.session.preliminary_fields['LAST-PAYMENT-DATE'].complaint_value
    apply_interactive_branch(e.session,'verify_last_payment','no')
    apply_interactive_branch(e.session,'prelim_correct_payment','unknown')
    assert e.session.last_payment_complaint is None
    assert script_condition(e.session,'complaint:LAST-PAYMENT-DATE')=='yes'
    assert e.session.preliminary_fields['LAST-PAYMENT-DATE'].complaint_value==original


def test_unknown_complaint_presence_blocks_instead_of_becoming_missing(scripted_engine):
    e=scripted_engine('cause_breach_dates')
    apply_interactive_branch(e.session,'verify_open_date','unknown')
    e._drain_hooks()
    assert e.current_node_id=='cause_breach_dates_resolve'
    assert not e.session.checkbox_selections
    e.submit("I don't know")
    assert e.current_node_id=='cause_breach_dates_resolve'
    assert e.session.defense_open_questions
    e.submit('no')
    assert e.current_node_id=='cause_breach_third_original'
    assert not e.session.defense_open_questions
    assert script_condition(e.session,'complaint:OPEN-DATE')=='no'


def test_fraud_question_uses_plaintiff_for_both_creditor_types(scripted_engine):
    from advocate_bot_qualtrics.practice_areas.consumer_debt.host_extras import render_node
    e=scripted_engine('fraud_hidden_facts',**{'PLAINTIFF.TYPE':'buyer'})
    text=render_node(e.current_node_id,None,e.session).question
    assert 'Did Example Bank give you false information' in text
    assert 'Example Bank or Example Original Bank' not in text


def test_original_creditor_recent_payment_finishes_sol_without_offering_boxes(scripted_engine):
    e=scripted_engine('statute_of_limitations_intro',**{'LAST.PAYMENT.DATE':'2025-12-01','COMPLAINT.DATE':'2026-01-01'})
    e._drain_hooks()
    assert e.submit('yes').current_node_id=='ambiguity_decision'
    assert e.session.defense_results['statute_of_limitations']['status']=='finished'
    assert 'statute_of_limitations' not in e.session.checkbox_selections


def test_sol_explicitly_uncertain_timing_uses_the_script_preservation_path(scripted_engine):
    e=scripted_engine('sol_payment_age')
    assert e.submit("I don't know").current_node_id=='statute_of_limitations_decision'
    assert not e.session.checkbox_selections


def test_unknown_oral_contract_answer_requires_clarification_for_that_option(scripted_engine):
    e=scripted_engine('sol_oral_gate')
    apply_interactive_branch(e.session,'prelim_oral','unknown')
    e._drain_hooks()
    assert e.current_node_id=='sol_oral_gate_resolve'
    e.submit("I don't know")
    assert e.session.defense_open_questions
    assert e.submit('yes').current_node_id=='sol_checkbox_second'
    assert not e.session.defense_open_questions


def test_original_creditor_complete_ownership_finishes_standing_without_an_offer(scripted_engine):
    e=scripted_engine('standing_privity_intro');e._drain_hooks()
    assert e.current_node_id=='failure_to_state_cause_confirm'
    assert e.session.defense_results['standing_privity']['status']=='finished'
    assert not e.session.checkbox_selections


@pytest.mark.parametrize('creditor,claim',[('original','breach'),('buyer','common'),('buyer','both')])
def test_negative_screening_answers_still_complete_all_sections(creditor,claim,scripted_engine):
    e=scripted_engine(**{'PLAINTIFF.TYPE':creditor,'SUIT.TYPE':claim});e._drain_hooks()
    for _ in range(150):
        if e.tree_complete:break
        n=TREE.node(e.current_node_id)
        branch='continue' if n.discussion_mode=='confirmation' else 'resolved' if n.discussion_mode=='referral' else 'English' if n.input else 'no'
        assert e.submit(branch).error is None
    else:pytest.fail('Negative traversal did not finish')
    assert set(e.session.defense_results)==set(DOCUMENTED_DEFENSES)
    assert not e.session.defense_open_questions
    assert all(value=='exclude' for boxes in e.session.checkbox_selections.values() for value in boxes.values())
