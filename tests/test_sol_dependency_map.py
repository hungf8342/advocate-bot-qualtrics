"""The approved SOL map traces checkbox offers backward to required facts."""
from itertools import product

import pytest

from advocate_bot_qualtrics.practice_areas.consumer_debt.sol_dependency_map import (
    affected_checkboxes, load_dependency_map, plan_checkbox_review,
)
from advocate_bot_qualtrics.practice_areas.consumer_debt.tree import INTERACTIVE_TREE_DEFINITION as TREE

QUESTIONS = {'plaintiff_type': 'sol_creditor_type_resolve', 'payment_timing': 'sol_payment_age', 'oral_agreement': 'sol_oral_gate_resolve'}


def plan(creditor, timing, oral, choices=None):
    return plan_checkbox_review({'plaintiff_type': creditor, 'payment_timing': timing, 'oral_agreement': oral}, QUESTIONS, choices or {})


@pytest.mark.parametrize('timing', [None, 'qualifying', 'recent', 'uncertain'])
def test_debt_buyers_always_offer_main_and_group_without_any_timing_fact(timing):
    result = plan('buyer', timing, 'no')
    assert result.availability == {'main': True, 'first': True, 'third': True, 'second': False}
    assert result.required_questions == ['statute_of_limitations_decision', 'sol_checkboxes_first_third']


def test_unknown_plaintiff_type_is_resolved_before_requesting_other_facts():
    result = plan(None, None, None)
    assert all(value is None for value in result.availability.values())
    assert result.required_questions == ['sol_creditor_type_resolve']


def test_recent_original_creditor_path_does_not_need_oral_fact_or_any_choices():
    result = plan('original', 'recent', None)
    assert not any(result.availability.values())
    assert result.required_questions == []


@pytest.mark.parametrize('creditor,timing,oral,expected', [
    ('buyer', None, 'yes', ['plaintiff_type', 'oral_agreement']),
    ('buyer', 'recent', 'no', ['plaintiff_type', 'oral_agreement']),
    ('original', 'recent', None, ['plaintiff_type', 'payment_timing']),
    ('original', 'qualifying', 'yes', ['plaintiff_type', 'payment_timing', 'oral_agreement']),
    ('original', 'uncertain', 'no', ['plaintiff_type', 'payment_timing', 'oral_agreement']),
])
def test_active_dependencies_exclude_facts_not_used_by_the_current_path(creditor, timing, oral, expected):
    assert plan(creditor, timing, oral).used_facts == expected


@pytest.mark.parametrize('timing', ['qualifying', 'uncertain'])
def test_preserved_original_creditor_path_requires_explicit_choices(timing):
    result = plan('original', timing, 'yes')
    assert all(result.availability.values())
    assert result.required_questions == ['statute_of_limitations_decision', 'sol_checkboxes_first_third', 'sol_checkbox_second']


def test_declining_main_does_not_remove_indented_choices():
    result = plan('buyer', None, 'yes', {'main': 'no'})
    assert result.required_questions == ['sol_checkboxes_first_third', 'sol_checkbox_second']
    assert all(result.availability.values())


def test_existing_choices_do_not_resolve_a_missing_required_fact():
    result = plan('original', None, 'yes', {'main': 'yes', 'first': 'yes', 'third': 'yes', 'second': 'yes'})
    assert result.required_questions == ['sol_payment_age']
    assert all(value is None for value in result.availability.values())


@pytest.mark.parametrize('field,expected', [
    ('guided_plaintiff', set()), ('guided_original_creditor', set()),
    ('guided_oral', {'second'}),
    ('guided_creditor_type', {'main', 'first', 'third', 'second'}),
    ('guided_payment_date', {'main', 'first', 'third', 'second'}),
    ('guided_filing_date', {'main', 'first', 'third', 'second'}),
    ('statute_of_limitations_decision', {'main'}),
    ('sol_checkboxes_first_third', {'first', 'third'}),
])
def test_backward_edges_identify_exactly_which_boxes_a_field_can_affect(field, expected):
    assert set(affected_checkboxes(field)) == expected


def test_map_points_to_existing_questions_for_the_exact_checkbox_ids():
    data = load_dependency_map()
    for box, spec in data['checkboxes'].items():
        assert box in {b.checkbox_id for b in TREE.node(spec['question']).selection_checkboxes}
    for fact in data['facts'].values():
        for question in fact['questions']:
            assert TREE.node(question).kind == 'choice'


@pytest.mark.parametrize('creditor,timing,oral', list(product(['original', 'buyer'], ['qualifying', 'recent', 'uncertain'], ['yes', 'no'])))
def test_map_offers_match_actual_script_traversal(creditor, timing, oral, scripted_engine):
    from advocate_bot_qualtrics.practice_areas.consumer_debt.session import apply_interactive_branch

    engine = scripted_engine('statute_of_limitations_intro', **{'PLAINTIFF.TYPE': creditor, 'LAST.PAYMENT.DATE': None})
    apply_interactive_branch(engine.session, 'prelim_oral', oral)
    engine._drain_hooks()
    offered = set()
    for _ in range(12):
        node = TREE.node(engine.current_node_id)
        if node.discussion_topic != 'Statute of Limitations' or node.discussion_mode == 'confirmation':
            break
        if node.selection_checkboxes:
            offered.update(box.checkbox_id for box in node.selection_checkboxes)
            branch = 'no'
        elif node.id == 'sol_payment_age':
            branch = {'qualifying': 'yes', 'recent': 'no', 'uncertain': 'unknown'}[timing]
        else:
            pytest.fail(f'Unexpected question {node.id}')
        assert engine.submit(branch).error is None
    else:
        pytest.fail('The SOL section did not finish')
    expected = plan(creditor, timing, oral)
    assert offered == {box for box, eligible in expected.availability.items() if eligible}
