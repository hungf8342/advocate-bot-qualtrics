"""October 25 routing for later defenses, reused facts, and staff resolution."""
import pytest
from advocate_bot_qualtrics.practice_areas.consumer_debt.affirmative_defenses import defense_summary
from advocate_bot_qualtrics.practice_areas.consumer_debt.host_extras import render_node
from advocate_bot_qualtrics.practice_areas.consumer_debt.session import apply_interactive_branch


def test_under_18_skips_both_mental_condition_questions(scripted_engine):
    e=scripted_engine('capacity_intro');e._drain_hooks()
    assert e.submit('yes').current_node_id=='capacity_decision'
    e.submit('no');e.submit('continue')
    assert 'capacity_incapacitated' not in e.session.defense_answers
    assert 'capacity_disclosure' not in e.session.defense_answers


@pytest.mark.parametrize('node,branch,target',[
 ('rescission_request_close','no','consideration_used_card'),
 ('rescission_refuse_close','no','consideration_used_card'),
 ('consideration_used_card','yes','accord_compliance'),
 ('consideration_other_user','yes','accord_compliance'),
 ('accord_compliance','no','excuse_unconsented_change'),
 ('waiver_payment_without_penalty','no','oral_modification_agreement'),
 ('oral_modification_agreement','no','tender_payment_refused'),
 ('tender_payment_refused','no','language_primary'),
 ('language_negotiation','no','review_questions'),
 ('language_contract','no','review_questions'),
])
def test_finish_routes_advance_without_offering_a_checkbox(node,branch,target,scripted_engine):
    e=scripted_engine(node);e.session.primary_language='Spanish' if node.startswith('language_') else None
    assert e.submit(branch).current_node_id==target
    assert not e.session.checkbox_selections
    assert any(r['status']=='finished' for r in e.session.defense_results.values())


@pytest.mark.parametrize('node', ['identity_referral_help','wrong_party_referral_help','capacity_staff_help','wrong_party_uncertain_help'])
def test_referral_requires_explicit_staff_resolution(node,scripted_engine):
    e=scripted_engine(node.removesuffix('_help'));e._drain_hooks()
    assert e.session.defense_open_questions
    assert e.submit("I don't know").current_node_id==node
    assert e.session.defense_open_questions
    e.submit('resolved')
    assert not e.session.defense_open_questions
    assert not e.session.checkbox_selections
    assert 'Clinic staff addressed this issue' in defense_summary(e.session)


def test_fact_uncertainty_requires_a_new_answer_and_retains_review_issue(scripted_engine):
    e=scripted_engine('waiver_payment_without_penalty')
    e.submit("I don't know")
    assert e.current_node_id=='waiver_uncertain_help'
    assert 'Open questions / clinic review:' in defense_summary(e.session)
    assert 'waiver' in defense_summary(e.session).lower()
    e.submit('retry')
    assert e.current_node_id=='waiver_payment_without_penalty'
    assert e.session.defense_open_questions
    e.submit('yes')
    assert e.current_node_id=='waiver_decision' and not e.session.defense_open_questions


def test_sequential_questions_are_asked_before_resolving_remaining_uncertainty(scripted_engine):
    e=scripted_engine('laches')
    assert e.submit("I don't know").current_node_id=='laches_statements'
    assert e.submit('no').current_node_id=='laches_lost_info'
    assert e.submit('no').current_node_id=='laches_unresolved_help'
    assert e.submit('retry').current_node_id=='laches_resolve'
    assert e.submit('yes').current_node_id=='laches_decision'
    assert not e.session.defense_open_questions


def test_credit_and_insurance_answers_are_reused_with_provenance(scripted_engine):
    e=scripted_engine('excuse_unconsented_change')
    apply_interactive_branch(e.session,'common_counts_uncredited','yes')
    apply_interactive_branch(e.session,'common_counts_insurance','no')
    e.submit('no')
    assert e.current_node_id=='excuse_modified'
    e.submit('no')
    assert e.current_node_id=='excuse_unreasonable'
    assert e.session.reused_answers['excuse_uncredited']=='common_counts_uncredited'
    assert e.session.reused_answers['excuse_insurance']=='common_counts_insurance'


def test_fraud_report_is_reused_even_when_user_does_not_select_fraud(scripted_engine):
    e=scripted_engine('fraud_hidden_facts')
    e.submit('yes');e.submit('no');e.submit('continue')
    e.current_node_id='common_counts_outcome';e._drain_hooks()
    assert e.current_node_id=='common_counts_decision'
    e.submit('yes')
    assert e.current_node_id=='common_counts_fifth_checkbox'
    assert e.session.defense_selections['fraud']=='exclude'


def test_consolidation_uses_the_approved_variant_in_questions_and_outcomes(scripted_engine):
    e=scripted_engine('rescission_intro')
    apply_interactive_branch(e.session,'prelim_consolidation','yes')
    e._drain_hooks()
    assert 'you or the debt consolidation company request' in render_node(e.current_node_id,None,e.session).question
    e.submit('yes')
    assert 'request by you or the debt consolidation company' in render_node(e.current_node_id,None,e.session).question
    e.submit('yes')
    assert 'request by you or the debt consolidation company' in render_node(e.current_node_id,None,e.session).question


def test_mitigation_asks_both_questions_before_followup_and_records_reason(scripted_engine):
    e=scripted_engine('mitigation_contact')
    assert e.submit("I don't know").current_node_id=='mitigation_settlement'
    assert e.submit('no').current_node_id=='mitigation_contact_uncertain'
    assert e.submit('I do not pick up unfamiliar calls').current_node_id=='mitigation_contact_resolve'
    assert e.session.mitigation_contact_reason=='I do not pick up unfamiliar calls'
    assert e.submit("I don't know").current_node_id=='mitigation_contact_help_help'
    assert e.session.defense_open_questions
    e.submit('retry');e.submit('yes')
    assert e.current_node_id=='failure_to_mitigate_confirm'
    assert not e.session.defense_open_questions
    assert not e.session.checkbox_selections


def test_clarified_payment_fact_is_reused_later_with_its_actual_source(scripted_engine):
    e=scripted_engine('common_counts_uncredited')
    e.submit("I don't know");e.submit('no');e.submit('no');e.submit('retry')
    assert e.current_node_id=='common_counts_uncredited_resolve'
    e.submit('yes')
    assert e.session.defense_answers['common_counts_uncredited']=='yes'
    e.current_node_id='excuse_unconsented_change'
    e.submit('no')
    assert e.current_node_id=='excuse_modified'
    assert e.session.defense_answers['excuse_uncredited']=='yes'
    assert e.session.reused_answers['excuse_uncredited']=='common_counts_uncredited_resolve'
    assert e.session.node_answers['excuse_uncredited'].confidence_pct==100


@pytest.mark.parametrize('node,target',[
    ('capacity_incapacitated','capacity_incapacitated'),
    ('language_contract','language_contract'),
])
def test_uncertainty_returns_to_the_specific_unresolved_question(node,target,scripted_engine):
    e=scripted_engine(node);e.session.primary_language='Spanish'
    e.submit("I don't know");e.submit('retry')
    assert e.current_node_id==target
    assert e.session.defense_open_questions
