"""Explicit choices for main, parent, and nested boxes; scoped Q&A and confirmations."""
import importlib

import pytest

from advocate_bot_qualtrics.core.schemas import ChatTurnResponse
from advocate_bot_qualtrics.practice_areas.consumer_debt.affirmative_defenses import defense_summary
from advocate_bot_qualtrics.practice_areas.consumer_debt.host_extras import render_node
from advocate_bot_qualtrics.practice_areas.consumer_debt.tree import INTERACTIVE_TREE_DEFINITION as TREE

BOX_NODES = [n for n in TREE.nodes if n.selection_checkboxes]


@pytest.mark.parametrize('definition', BOX_NODES, ids=lambda n:n.id)
@pytest.mark.parametrize('branch,selection',[('yes','include'),('no','exclude')])
def test_each_decision_records_only_its_explicit_checkbox_choices(definition,branch,selection,scripted_engine):
    e=scripted_engine(definition.id)
    # Apply through the same validated metadata binding as the engine, without
    # traversing unrelated downstream questions for this exhaustive storage check.
    e.bundle.apply_branch(e.session,definition.id,branch)
    boxes = definition.selection_checkboxes
    assert e.session.checkbox_selections == {boxes[0].defense_id:{box.checkbox_id:selection for box in boxes}}
    assert e.session.defense_selections == {box.defense_id:selection for box in boxes if box.checkbox_id=='main'}


@pytest.mark.parametrize('definition',BOX_NODES,ids=lambda n:n.id)
def test_uncertain_checkbox_stays_local_until_an_explicit_choice(definition,scripted_engine):
    e=scripted_engine(definition.id)
    step=e.submit("I don't know")
    assert step.error is None
    assert not e.session.checkbox_selections
    assert e.session.defense_open_questions
    assert not step.tree_complete
    assert 'move on' not in '\n'.join(step.assistant_messages)
    e.submit('retry')
    assert e.current_node_id==definition.id
    assert e.session.defense_open_questions  # Readiness to retry does not resolve a choice.
    e.submit('no')
    for box in definition.selection_checkboxes:
        assert e.session.checkbox_selections[box.defense_id][box.checkbox_id]=='exclude'
    assert not e.session.defense_open_questions


@pytest.mark.parametrize('branch,mark,selection', [('yes','x','include'),('no',' ','exclude')])
def test_grouped_sol_choice_records_both_boxes_and_waits_for_readiness(branch,mark,selection,scripted_engine):
    e=scripted_engine('sol_guidance',**{'PLAINTIFF.TYPE':'buyer'})
    e._drain_hooks()
    assert e.current_node_id=='sol_checkboxes_first_third'
    assert 'both the first and third' in render_node(e.current_node_id,None,e.session).question
    assert e.submit(branch).current_node_id=='statute_of_limitations_confirm'
    assert e.session.checkbox_selections['statute_of_limitations']=={'first':selection,'third':selection}
    text=render_node(e.current_node_id,None,e.session).question
    assert f'[{mark}] the first' in text and f'[{mark}] the third' in text
    assert e.submit("I don't know").current_node_id=='statute_of_limitations_confirm'
    assert e.submit('continue').current_node_id=='ambiguity_decision'
    assert 'main' not in e.session.checkbox_selections['statute_of_limitations']


def test_parent_choice_does_not_select_children_or_main(scripted_engine):
    e=scripted_engine('cause_breach_parent',**{'OWNERSHIP':False})
    assert e.submit('no').current_node_id=='cause_breach_main'
    assert e.session.checkbox_selections=={'failure_to_state_cause':{'breach_parent':'exclude'}}
    e.submit('yes')
    assert e.session.checkbox_selections['failure_to_state_cause']['main']=='include'


def test_same_main_box_is_not_asked_again_for_second_claim_group(scripted_engine):
    e=scripted_engine('cause_breach_main',**{'OWNERSHIP':False})
    e.submit('no')
    assert e.current_node_id=='cause_common_second_original'
    e.submit('yes')
    assert e.current_node_id=='cause_common_parent'
    step=e.submit('yes')
    assert step.current_node_id=='failure_to_state_cause_confirm'
    assert e.session.reused_answers['cause_common_main']=='cause_breach_main'
    assert e.session.defense_selections['failure_to_state_cause']=='exclude'


@pytest.mark.parametrize('intent,branch',[('ask_about_complaint','yes'),('off_topic','no')])
def test_real_model_validation_does_not_advance_on_nonanswers(monkeypatch,scripted_engine,intent,branch):
    from advocate_bot_qualtrics.core import engine as engine_module
    module=importlib.import_module('advocate_bot_qualtrics.core.process_chat')
    e=scripted_engine('ambiguity_decision')
    monkeypatch.setattr(engine_module,'process_chat',module.process_chat)
    monkeypatch.setattr(module,'submit_chat_turn',lambda **kw:ChatTurnResponse(user_intent=intent,assistant_reply='An approved explanation.',next_node_id=branch))
    step=e.submit('What does this mean?')
    assert step.error is None and step.branch_id is None
    assert step.current_node_id=='ambiguity_decision'
    assert not e.session.checkbox_selections


def test_real_model_validation_rejects_an_undeclared_branch(monkeypatch,scripted_engine):
    from advocate_bot_qualtrics.core import engine as engine_module
    module=importlib.import_module('advocate_bot_qualtrics.core.process_chat')
    e=scripted_engine('ambiguity_decision')
    monkeypatch.setattr(engine_module,'process_chat',module.process_chat)
    monkeypatch.setattr(module,'submit_chat_turn',lambda **kw:ChatTurnResponse(user_intent='answer_node',assistant_reply='Recorded.',next_node_id='standing_privity_intro',answer_confidence_pct=100))
    step=e.submit('yes')
    assert step.current_node_id=='ambiguity_decision'
    assert not e.session.checkbox_selections


def test_reset_clears_boxes_factual_resolutions_and_clinic_issues(scripted_engine):
    e=scripted_engine('ambiguity_decision')
    e.submit('yes')
    e.session.script_facts['field:ORAL']='yes'
    e.session.defense_open_questions['test']={'defense':'ambiguity','reason':'Unresolved','retry_node':'ambiguity_decision'}
    e.reset()
    assert not e.session.checkbox_selections and not e.session.script_facts
    assert not e.session.defense_open_questions and not e.session.script_visited
    assert e.current_node_id=='verify_case_number'


def test_sol_combined_choice_keeps_oral_box_independent(scripted_engine):
    from advocate_bot_qualtrics.practice_areas.consumer_debt.session import apply_interactive_branch

    engine = scripted_engine('sol_guidance', **{'PLAINTIFF.TYPE': 'buyer'})
    apply_interactive_branch(engine.session, 'prelim_oral', 'yes')
    engine._drain_hooks()
    assert engine.submit('no').current_node_id == 'sol_checkbox_second'
    assert engine.session.checkbox_selections['statute_of_limitations'] == {'first': 'exclude', 'third': 'exclude'}
    assert engine.submit('yes').current_node_id == 'statute_of_limitations_confirm'
    assert engine.session.checkbox_selections['statute_of_limitations'] == {'first': 'exclude', 'third': 'exclude', 'second': 'include'}
