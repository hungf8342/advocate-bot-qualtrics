"""November 7 source: scope, nested choices, uncertainty, and full traversal."""
import pytest

from advocate_bot_qualtrics.practice_areas.consumer_debt.guided_sol import (
    COMPLETE, CONTENT, DEFENSES, TREE, GuidedAdvanceRequest, GuidedEditRequest,
    GuidedRequest, GuidedSolReview, advance_review, edit_review,
)
from test_guided_sol import intake, review, advance_updated, default_answer


def reach(defense, *, suit='both', consolidation='no', recognize='yes'):
    history = intake('buyer')
    values = {'guided_suit_type': suit, 'guided_consolidation': consolidation, 'guided_recognize': recognize}
    history = [a.model_copy(update={'value': values[a.node_id]}) if a.node_id in values else a for a in history]
    current = review(history)
    from advocate_bot_qualtrics.practice_areas.consumer_debt.guided_sol import PRESENTATION
    combined = defense in PRESENTATION['explanation_on_question']
    target = TREE.node(defense+'_intro').next if combined else DEFENSES[defense].get('intro', defense + '_decision')
    for _ in range(250):
        if current.current == target:
            return advance_updated(current, 'continue') if 'intro' in DEFENSES[defense] and not combined else current
        current = advance_updated(current, default_answer(current))
    raise AssertionError(target)


def submit(current, *values):
    for value in values:
        current = advance_updated(current, value)
        current.page()  # Every intermediate page and clarification context must render.
    return current


def test_scope_and_source_are_november_7():
    assert [d['number'] for d in DEFENSES.values()] == [1, 2, 5, 8, *range(9, 22)]
    assert not {'standing_privity', 'failure_to_state_cause', 'wrong_party', 'identity_theft'} & DEFENSES.keys()
    assert '2026-11-07' in CONTENT['source']
    assert 'may still need to prove when you last paid' in CONTENT['nodes']['statute_of_limitations_intro']['explanation']
    assert 'Ambiguity means something is unclear' in CONTENT['nodes']['ambiguity_intro']['explanation']
    assert 'Laches may apply if:' in CONTENT['nodes']['laches_intro']['explanation']


@pytest.mark.parametrize('defense', list(DEFENSES)[2:])
def test_each_added_section_can_finish_and_render_summary(defense):
    current = reach(defense)
    for _ in range(50):
        if current.current == DEFENSES[defense]['summary']:
            page = current.page()
            assert page['section'] == DEFENSES[defense]['label']
            assert page['open_questions'] == []
            return
        current = submit(current, default_answer(current))
    raise AssertionError(defense)


@pytest.mark.parametrize('selected', ['yes', 'no'])
def test_common_counts_broad_first_offer_and_parent_derive_from_choices(selected):
    current = reach('common_counts')
    assert current.current == 'common_counts_first_checkbox'
    assert 'miscalculate' in ' '.join(current.page()['body'])
    current = submit(current, selected, 'no', 'no')
    assert current.current == DEFENSES['common_counts']['summary']
    choices = current.session.checkbox_selections['common_counts']
    assert choices == {'first': 'include' if selected == 'yes' else 'exclude',
                       'main': 'include' if selected == 'yes' else 'exclude'}
    assert len(current.page()['rows']) == 6
    assert next(r for r in current.page()['rows'] if r['id'] == 'main')['edit_index'] is None


def test_excuse_offers_second_and_fifth_without_factual_screening():
    current = reach('excuse_breach')
    assert current.current == 'excuse_unconsented_change'
    current = submit(current, 'no')
    assert current.current == 'excuse_second_checkbox'
    current = submit(current, 'no', 'no', 'no')
    assert current.current == 'excuse_fifth_checkbox'
    assert 'good faith and fair dealing' in ' '.join(current.page()['body'])
    current = submit(current, 'yes')
    assert current.current == DEFENSES['excuse_breach']['summary']
    assert current.session.checkbox_selections['excuse_breach'] == {'second': 'exclude', 'fifth': 'include', 'main': 'include'}


def test_fraud_fact_alone_does_not_offer_common_counts_fifth():
    current = reach('fraud')
    current = submit(current, 'yes', 'no')
    # Keep the factual Yes, but explicitly decline the Fraud defense.
    while current.current != DEFENSES['common_counts']['intro']:
        current = submit(current, default_answer(current))
    current = submit(current, 'continue', 'no', 'no', 'no')
    assert current.current == DEFENSES['common_counts']['summary']
    assert 'fifth' not in current.session.checkbox_selections['common_counts']


def test_selected_fraud_offers_common_counts_fifth_and_requires_separate_choice():
    current = reach('fraud')
    current = submit(current, 'yes', 'yes')
    while current.current != DEFENSES['common_counts']['intro']:
        current = submit(current, default_answer(current))
    current = submit(current, 'continue', 'no', 'no', 'no')
    assert current.current == 'common_counts_fifth_checkbox'
    assert not current.session.checkbox_selections['common_counts'].get('fifth')
    current = submit(current, 'no')
    assert current.session.checkbox_selections['common_counts']['main'] == 'exclude'


@pytest.mark.parametrize('suit,defense', [('breach','common_counts'), ('common','excuse_breach')])
def test_claim_type_finishes_inapplicable_section_without_offers(suit, defense):
    current = reach(defense, suit=suit)
    assert current.current == DEFENSES[defense]['summary']
    assert all(r['status'] == 'Not offered on this path' for r in current.page()['rows'])


def test_mitigation_nested_options_derive_parent_and_keep_consolidation_wording():
    current = reach('failure_to_mitigate', consolidation='yes')
    assert 'debt consolidation company' in current.page()['title']
    current = submit(current, 'no', 'yes')
    assert current.current == 'mitigation_first_checkbox'
    assert 'debt consolidation company' in ' '.join(current.answer_response)
    assert current.page()['body'] == []
    current = submit(current, 'no')
    assert current.current == 'mitigation_second_checkbox'
    current = submit(current, 'yes')
    assert current.session.checkbox_selections['failure_to_mitigate'] == {'first': 'exclude', 'second': 'include', 'main': 'include'}


def test_mitigation_contact_uncertainty_gets_clarification_then_second_offer():
    current = reach('failure_to_mitigate')
    current = submit(current, 'unknown', 'no')
    assert current.current == 'mitigation_contact_uncertain'
    assert current.page()['input_type'] == 'text'
    assert current.page()['allow_unknown']
    current = submit(current, 'I do not pick up calls', 'unknown')
    assert current.current == 'mitigation_second_checkbox'
    assert current.session.defense_answers['mitigation_contact'] == 'unknown'


def test_unknown_screening_and_checkbox_choice_never_become_no():
    current = reach('waiver')
    current = submit(current, 'unknown')
    assert current.current == 'waiver_uncertain_help'
    assert current.session.defense_open_questions
    assert 'waiver' not in current.session.checkbox_selections
    current = submit(current, 'retry', 'yes', 'unknown')
    assert current.current == 'waiver_decision_unresolved_help'
    current = submit(current, 'retry', 'no')
    assert not current.session.defense_open_questions
    assert current.current == DEFENSES['waiver']['summary']


@pytest.mark.parametrize('translated,expected', [('yes', 'guided_language_1632_summary'), ('no', 'language_1632_decision')])
def test_language_translation_question_uses_positive_wording_and_correct_polarity(translated, expected):
    current = reach('language_1632')
    assert current.current == 'language_primary'
    current = submit(current, 'Spanish')
    assert current.current == 'language_negotiation'
    assert current.page()['title'] == 'Did you apply for the credit card in Spanish?'
    current = submit(current, 'yes')
    assert 'give you the credit card agreement' in current.page()['title']
    assert current.page()['input_type'] == 'choice'
    current = submit(current, translated)
    assert current.current == expected


def test_capacity_minor_skips_mental_condition_and_staff_referral_blocks():
    current = submit(reach('capacity'), 'yes')
    assert current.current == 'capacity_decision'
    current = submit(reach('capacity'), 'no', 'yes', 'no')
    assert current.current == 'capacity_staff_help'
    current = submit(current, 'unknown')
    assert current.current == 'capacity_staff_help'
    current = submit(current, 'resolved')
    assert current.current == DEFENSES['capacity']['summary']
    assert not current.session.checkbox_selections.get('capacity')


def test_full_affirmative_path_exceeds_old_history_limit_and_final_review_has_every_box():
    current = review(intake('buyer', oral='yes'))
    seen = set()
    for _ in range(300):
        if current.current == COMPLETE:
            break
        seen.add(current._current_defense())
        node = TREE.node_map.get(current.current)
        value = 'continue' if current.current.startswith('guided_') else 'yes'
        if node and node.kind == 'input': value = 'Spanish'
        if current.current == 'language_contract': value = 'no'
        current = submit(current, value)
    assert current.current == COMPLETE
    assert len(current.history) > 80
    assert seen == set(DEFENSES)
    assert GuidedRequest(history=current.history).history == current.history
    assert len(current.page()['groups']) == 17
    assert all(g['rows'] for g in current.page()['groups'])
    assert not current.page()['open_questions']
    assert not any(TREE.node(a.node_id).discussion_topic in {'Identity Theft','Wrong Party','Standing and Privity','Failure to State a Cause of Action'} for a in current.history if a.node_id in TREE.node_map)


def test_editing_excuse_fact_removes_invalid_nested_choice_but_keeps_broad_choices():
    current = submit(reach('excuse_breach'), 'yes', 'yes', 'yes', 'no', 'no', 'no')
    assert current.current == DEFENSES['excuse_breach']['summary']
    index = next(i for i,a in enumerate(current.history) if a.node_id == 'excuse_unconsented_change')
    updated = edit_review({}, GuidedEditRequest(history=current.history, edit_index=index, value='no'))
    assert updated.current == DEFENSES['excuse_breach']['summary']
    assert updated.session.checkbox_selections['excuse_breach'] == {'second':'include','fifth':'exclude','main':'include'}


def test_unresolved_shared_consolidation_returns_to_intake_then_resumes():
    defense = 'failure_to_mitigate'
    current = reach(defense, consolidation='unknown')
    assert current.current == 'guided_consolidation'
    assert current.page()['section'] == 'Preliminary fields'
    current = submit(current, 'unknown')
    assert current.current == 'guided_consolidation'
    current = submit(current, 'yes')
    assert current.page()['section'] == DEFENSES[defense]['label']
    assert current.session.preliminary_fields['CONSOLIDATION'].value == 'yes'
    assert 'debt consolidation company' in current.page()['title']


def test_changed_fraud_selection_invalidates_dependent_common_counts_option():
    current = submit(reach('fraud'), 'yes', 'yes')
    while current.current != DEFENSES['common_counts']['intro']:
        current = submit(current, default_answer(current))
    current = submit(current, 'continue', 'no', 'no', 'no', 'yes')
    assert current.session.checkbox_selections['common_counts']['fifth'] == 'include'
    index = next(i for i,a in enumerate(current.history) if a.node_id == 'fraud_decision')
    current = edit_review({}, GuidedEditRequest(history=current.history, edit_index=index, value='no'))
    while current.current != DEFENSES['common_counts']['summary']:
        current = submit(current, default_answer(current))
    assert 'fifth' not in current.session.checkbox_selections['common_counts']
    assert current.session.checkbox_selections['common_counts']['main'] == 'exclude'
    # Reoffering the box needs a fresh explicit choice.
    index = next(i for i,a in enumerate(current.history) if a.node_id == 'fraud_decision')
    current = edit_review({}, GuidedEditRequest(history=current.history, revision=current.revision, edit_index=index, value='yes'))
    while current.current != 'common_counts_fifth_checkbox':
        assert current.current != DEFENSES['common_counts']['summary']
        current = submit(current, default_answer(current))
    assert 'fifth' not in current.session.checkbox_selections['common_counts']


@pytest.mark.parametrize('defense', ['rescission', 'accord_satisfaction'])
def test_later_sections_reuse_consolidation_resolved_in_mitigation(defense):
    current = reach(defense, consolidation='yes')
    assert current.page()['section'] == DEFENSES[defense]['label']
    assert current.current != 'guided_consolidation'
    assert 'debt consolidation company' in current.page()['title']


def test_unrelated_edit_retains_explicitly_uncertain_mitigation_contact():
    current = submit(reach('failure_to_mitigate'), 'unknown', 'no', 'I do not pick up calls', 'unknown', 'no')
    assert current.current == DEFENSES['failure_to_mitigate']['summary']
    index = next(i for i,a in enumerate(current.history) if a.node_id == 'guided_plaintiff')
    current = edit_review({}, GuidedEditRequest(history=current.history, edit_index=index, value='Renamed Bank'))
    for _ in range(30):
        if current.current == DEFENSES['failure_to_mitigate']['summary']:
            break
        assert current.current.startswith('guided_')
        current = submit(current, 'continue')
    assert current.current == DEFENSES['failure_to_mitigate']['summary']
    assert current.session.defense_answers['mitigation_contact'] == 'unknown'
    assert current.session.checkbox_selections['failure_to_mitigate']['second'] == 'exclude'
