"""Litigants select defenses; clarification and scoped Q&A cannot select for them."""

from dataclasses import replace
import importlib
from pathlib import Path
import re
import runpy

import pytest
from pydantic import ValidationError

from advocate_bot_qualtrics.core.bundle import get_bundle
from advocate_bot_qualtrics.core.engine import InteractiveChatEngine
from advocate_bot_qualtrics.core.schemas import ChatTurnResponse
from advocate_bot_qualtrics.core.tree_definition import TreeDefinition
from advocate_bot_qualtrics.practice_areas.consumer_debt.affirmative_defenses import (
    DOCUMENTED_DEFENSES, assess_defense, defense_summary,
)
from advocate_bot_qualtrics.practice_areas.consumer_debt.host_extras import render_node
from advocate_bot_qualtrics.practice_areas.consumer_debt.session import apply_interactive_branch, init_session
from advocate_bot_qualtrics.practice_areas.consumer_debt.tree import INTERACTIVE_TREE_DEFINITION as TREE

chat_module = importlib.import_module('advocate_bot_qualtrics.core.process_chat')


def engine_at(node, tmp_path):
    bundle = replace(get_bundle('consumer_debt'), get_session_fields_xlsx_path=lambda: tmp_path / 'fields.xlsx')
    engine = InteractiveChatEngine.from_user_input(bundle=bundle)
    engine.current_node_id = node
    return engine


@pytest.fixture
def model_reply(monkeypatch):
    """Exercise process_chat's real routing validation with controlled model output."""
    replies, payloads = [], []

    def submit(*, system, payload):
        payloads.append((system, payload))
        assert replies, 'Unexpected model call'
        return replies.pop(0)

    monkeypatch.setattr(chat_module, 'submit_chat_turn', submit)
    return replies, payloads


def answer(branch):
    return ChatTurnResponse(user_intent='answer_node', assistant_reply='Recorded.',
                            next_node_id=branch, answer_confidence_pct=100)


@pytest.mark.parametrize('defense', DOCUMENTED_DEFENSES)
@pytest.mark.parametrize('choice,selection', [('yes', 'include'), ('no', 'exclude')])
def test_every_defense_requires_and_records_a_litigant_choice(defense, choice, selection, tmp_path, model_reply):
    replies, _ = model_reply
    engine = engine_at(defense + '_result', tmp_path)
    messages = engine._drain_hooks()
    assert engine.current_node_id == defense + '_decision'
    assert engine.session.defense_selections == {}
    assert not any(re.search(r'\b(?:checked|unchecked)\b|Result:|Personalized Application', text) for text in messages)
    internal = engine.session.defense_results[defense].copy()
    replies.append(answer(choice))
    step = engine.submit(choice)
    assert step.error is None
    assert engine.session.defense_selections[defense] == selection
    assert engine.session.defense_results[defense] == internal
    assert step.current_node_id != defense + '_decision'
    assert not any(re.search(r'\b(?:checked|unchecked)\b|Result:|Personalized Application', text) for text in step.assistant_messages)


@pytest.mark.parametrize('defense', DOCUMENTED_DEFENSES)
def test_unknown_never_selects_or_skips_a_defense(defense, tmp_path, model_reply):
    replies, payloads = model_reply
    engine = engine_at(defense + '_decision', tmp_path)
    step = engine.submit("I don't know")
    assert step.current_node_id == defense + '_clarify'
    assert 'clarifying questions' in '\n'.join(step.assistant_messages)
    assert 'move on' not in '\n'.join(step.assistant_messages)
    assert engine.session.defense_selections == {}
    assert not step.tree_complete
    assert payloads == []  # Bare uncertainty is handled without a model call.
    replies.append(answer('no'))
    step = engine.submit('No, I have no questions')
    assert step.current_node_id == defense + '_decision'
    assert engine.session.defense_selections == {}
    assert not step.tree_complete


@pytest.mark.parametrize('mode', ['decision', 'clarify', 'questions'])
def test_related_question_is_answered_without_advancing_or_making_a_selection(mode, tmp_path, model_reply):
    replies, payloads = model_reply
    engine = engine_at('statute_of_limitations_' + mode, tmp_path)
    engine.session.defense_answers['sol_creditor_type'] = 'buyer'
    assess_defense(engine.session, 'statute_of_limitations')
    replies.append(ChatTurnResponse(user_intent='ask_about_complaint',
        assistant_reply='The one-year rule is a preservation screen, separate from the legal deadline.',
        next_node_id='yes'))  # Invalid advancement on a non-answer is cleared by the validator.
    step = engine.submit('Is the one-year screen the legal deadline?')
    assert step.error is None
    assert step.current_node_id == 'statute_of_limitations_' + mode
    assert step.assistant_messages[0] == 'The one-year rule is a preservation screen, separate from the legal deadline.'
    assert step.branch_id is None
    assert engine.session.defense_selections == {}
    context = payloads[0][1]['current_node']
    assert context['discussion_topic'] == 'Statute of Limitations'
    assert 'debt buyers' in context['explanation']['text']
    assert ': checked' not in context['explanation']['text']
    assert 'Do not infer a selection' in payloads[0][0]


def test_unrelated_question_redirects_to_current_defense_without_advancing(tmp_path, model_reply):
    replies, _ = model_reply
    engine = engine_at('statute_of_limitations_questions', tmp_path)
    replies.append(ChatTurnResponse(user_intent='off_topic', assistant_reply='Unrelated answer.', next_node_id='include'))
    step = engine.submit('Tell me about laches instead')
    assert step.error is None
    assert step.current_node_id == 'statute_of_limitations_questions'
    assert 'Let’s finish Statute of Limitations first' in step.assistant_messages[0]
    assert 'Unrelated answer' not in '\n'.join(step.assistant_messages)
    assert engine.session.defense_selections == {}


@pytest.mark.parametrize('node', ['ambiguity_clarify', 'ambiguity_questions'])
@pytest.mark.parametrize('branch,selection', [('include', 'include'), ('exclude', 'exclude')])
def test_explicit_choice_during_clarification_moves_on_without_an_extra_confirmation(node, branch, selection, tmp_path, model_reply):
    replies, _ = model_reply
    engine = engine_at(node, tmp_path)
    replies.append(answer(branch))
    step = engine.submit('I want to check it off' if branch == 'include' else "I don't want to check it off")
    assert step.error is None
    assert engine.session.defense_selections['ambiguity'] == selection
    assert step.current_node_id == 'standing_privity_decision'


def test_litigant_can_decline_a_preservation_screen_and_summary_uses_their_choice():
    session = init_session()
    session.defense_answers['sol_creditor_type'] = 'buyer'
    assess_defense(session, 'statute_of_limitations')
    assert session.defense_results['statute_of_limitations']['status'] == 'checked'
    assert session.defense_selections == {}
    apply_interactive_branch(session, 'statute_of_limitations_decision', 'no')
    summary = defense_summary(session)
    assert 'Statute of limitations: You chose not to include this defense.' in summary
    assert ': checked' not in summary and ': unchecked' not in summary
    assert session.defense_results['statute_of_limitations']['status'] == 'checked'


def test_choice_does_not_remove_a_clinic_referral():
    session = init_session()
    session.defense_answers.update(identity_recognize='no', identity_suspected='yes')
    assess_defense(session, 'identity_theft')
    apply_interactive_branch(session, 'identity_theft_decision', 'yes')
    summary = defense_summary(session)
    assert 'You chose to include this defense.' in summary
    assert 'notify clinic staff' in summary
    assert 'Open questions / clinic review:' in summary


def test_all_decision_routes_keep_uncertainty_local_and_cannot_auto_reuse_facts():
    from advocate_bot_qualtrics.practice_areas.consumer_debt.host_extras import skip_collected_date_node
    session = init_session()
    for key in DOCUMENTED_DEFENSES:
        decision = TREE.node(key + '_decision')
        assert decision.discussion_mode == 'decision'
        assert {b.id for b in decision.branches} == {'yes', 'no', 'unknown'}
        assert TREE.route(decision.id, 'unknown') == key + '_clarify'
        assert skip_collected_date_node(decision.id, session) == decision.id
        assert TREE.route(key + '_clarify', 'no') == decision.id
        assert TREE.route(key + '_questions', 'ready') == decision.id
        assert set(decision.validation.categories) == {b.id for b in decision.branches}


def test_interface_combines_assistant_turn_and_shows_one_header(tmp_path):
    demo = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'scripts/interactive_chat_demo.py'))
    engine = engine_at('statute_of_limitations_intro', tmp_path)
    apply_interactive_branch(engine.session, 'prelim_creditor_type', 'buyer')
    engine._drain_hooks()
    engine._append_next_question()
    bubbles = demo['_chat_history'](engine)
    assert len(bubbles) == 1
    text = bubbles[0]['content']
    assert text.count('### Statute of Limitations') == 1
    assert text.index('Statute of limitations is a rule') < text.index("debt buyers often don't have records") < text.index('Do you want to check off')
    assert 'Personalized Application' not in text and 'Result:' not in text
    assert ': checked' not in text and ': unchecked' not in text


def test_reset_clears_litigant_choices(tmp_path):
    engine = engine_at('ambiguity_decision', tmp_path)
    apply_interactive_branch(engine.session, 'ambiguity_decision', 'yes')
    engine.reset()
    assert engine.session.defense_selections == {}
    assert engine.current_node_id == 'verify_case_number'


def test_discussion_metadata_requires_a_topic_and_mode_together():
    data = TREE.model_dump()
    data['nodes'][0]['discussion_mode'] = 'decision'
    with pytest.raises(ValidationError, match='both discussion topic and mode'):
        TreeDefinition.model_validate(data)
