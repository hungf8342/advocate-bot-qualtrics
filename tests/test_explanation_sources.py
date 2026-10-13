"""Only the explanation documents supply active questions and conditional routing."""

from pathlib import Path
from zipfile import ZipFile
import xml.etree.ElementTree as ET

import pytest
from pydantic import ValidationError

from advocate_bot_qualtrics.core.engine import InteractiveChatEngine
from advocate_bot_qualtrics.core.tree_definition import TreeDefinition
from advocate_bot_qualtrics.practice_areas.consumer_debt.affirmative_defenses import DOCUMENTED_DEFENSES, assess_defense
from advocate_bot_qualtrics.practice_areas.consumer_debt.host_extras import render_node, skip_collected_date_node
from advocate_bot_qualtrics.practice_areas.consumer_debt.session import init_session
from advocate_bot_qualtrics.practice_areas.consumer_debt.tree import INTERACTIVE_TREE_DEFINITION as TREE


def paragraphs(filename):
    path = Path(__file__).resolve().parents[1] / 'docs/source-material/2026-10-11' / filename
    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    with ZipFile(path) as doc:
        root = ET.fromstring(doc.read('word/document.xml'))
    return [''.join(t.text or '' for t in p.findall('.//w:t', ns)).strip()
            for p in root.findall('.//w:p', ns)]


def test_active_defenses_exactly_match_the_nine_documented_sections():
    actual = [n.action.removeprefix('assess_') for n in TREE.nodes if n.action and n.action.startswith('assess_')]
    assert actual == list(DOCUMENTED_DEFENSES)
    assert len(actual) == 9
    for node in ('fraud_decision', 'fraud_clarify', 'fraud_questions'):
        for branch in TREE.node(node).branches:
            if branch.id in {'yes', 'no'} and node.endswith('_decision') or branch.id in {'include', 'exclude'}:
                assert branch.target == 'review_questions'
    assert 'mitigation_consolidation' not in TREE.node_map
    assert 'language_1632' not in TREE.node_map


def test_document_conditionals_do_not_become_additional_factual_quizzes():
    from advocate_bot_qualtrics.practice_areas.consumer_debt.tree import INTERACTIVE_CONDITIONAL_ROUTE_NODES

    assert INTERACTIVE_CONDITIONAL_ROUTE_NODES == {n.id for n in TREE.nodes if n.kind == 'condition'}
    actual = {n.id for n in TREE.nodes if n.kind == 'choice' and n.discussion_mode == 'screening'}
    assert actual == {
        'sol_payment_estimate_agree', 'sol_payment_age',
        'identity_suspected', 'identity_help', 'wrong_party_owner', 'wrong_party_help',
        'laches', 'laches_statements', 'laches_lost_info', 'fraud_hidden_facts',
    }
    for n in TREE.nodes:
        if n.kind == 'condition':
            assert n.question == ''
            assert n.explanation is None
            assert 'unknown' in {b.id for b in n.branches}
            assert skip_collected_date_node(n.id, init_session()) != n.id


@pytest.mark.parametrize('defense', ['ambiguity', 'mistake'])
def test_general_only_sections_go_directly_to_choice_without_added_application(defense):
    engine = InteractiveChatEngine.from_user_input()
    engine.current_node_id = defense + '_intro'
    messages = engine._drain_hooks()
    assert engine.current_node_id == defense + '_decision'
    assert defense not in TREE.node_map
    assert len(messages) == 1
    assert TREE.node(defense + '_intro').explanation.text in messages[0]
    assert engine.session.defense_results[defense]['status'] == 'informational'
    assert engine.session.defense_results[defense]['reason'] == ''
    assert engine.session.defense_selections == {}


@pytest.mark.parametrize('node', ['sol_creditor_type', 'standing_creditor_type', 'cause_creditor_type', 'fraud_creditor_type'])
def test_missing_intake_facts_take_unknown_condition_path_without_asking_again(monkeypatch, node):
    from advocate_bot_qualtrics.core import engine as engine_module
    monkeypatch.setattr(engine_module, 'process_chat', lambda *args: pytest.fail('Conditions cannot ask the model'))
    engine = InteractiveChatEngine.from_user_input()
    engine.current_node_id = node
    engine._drain_hooks()
    assert TREE.node(engine.current_node_id).discussion_mode == 'decision'
    assert engine.session.reused_answers[node] == 'preliminary_intake'
    assert engine.session.defense_selections == {}


def test_preliminary_explanation_paragraphs_come_from_current_document():
    approved = set(paragraphs('2026.10.11 explanations-prelim-questions.docx'))
    for node in TREE.nodes:
        if node.id == 'statute_of_limitations_intro':
            break
        if node.explanation is None:
            continue
        texts = [b.text for b in node.explanation.blocks] or [node.explanation.text]
        for text in texts:
            assert text in approved or text == '{complaint_payment_restatement}', (node.id, text)


@pytest.mark.parametrize('node', ['identity_suspected', 'wrong_party_owner', 'laches', 'laches_statements', 'laches_lost_info'])
def test_factual_question_wording_comes_from_defense_document(node):
    approved = paragraphs('2026.10.11 explanations-aff-defenses.docx')
    question = TREE.node(node).question
    assert any(p == question or p.startswith(question + ' [') for p in approved)


@pytest.mark.parametrize('recognition,question', [
    ('no', 'Do you have further questions on how to determine whether this account exists because of ID theft?'),
    ('unknown', 'Do you have further questions on how to determine whether this account belongs to you or not?'),
])
def test_identity_uncertainty_uses_the_matching_document_branch(recognition, question):
    session = init_session()
    session.defense_answers['identity_recognize'] = recognition
    assert render_node('identity_help', None, session).question.endswith(question)
    assert any(p.endswith(question) for p in paragraphs('2026.10.11 explanations-aff-defenses.docx'))


def test_buyer_date_application_requires_a_confirmed_qualifying_attachment():
    session = init_session()
    session.defense_answers.update(cause_creditor_type='buyer', cause_statement='unknown',
                                   cause_purchase_documents='unknown', cause_breach_contract='yes',
                                   cause_open_date='no', cause_breach_date='no')
    assess_defense(session, 'failure_to_state_cause')
    assert session.defense_results['failure_to_state_cause']['status'] == 'unresolved'


def test_fraud_does_not_assume_original_creditor_when_type_is_unknown():
    session = init_session()
    session.defense_answers['identity_suspected'] = 'no'
    assert skip_collected_date_node('fraud_identity', session) == 'fraud_result'
    assert 'fraud_hidden_facts' not in session.defense_answers


def test_condition_schema_rejects_a_user_question():
    with pytest.raises(ValidationError, match='cannot ask a question'):
        TreeDefinition.model_validate({
            'id': 'invalid', 'version': '1', 'start_node_id': 'gate',
            'nodes': [
                {'id': 'gate', 'kind': 'condition', 'question': 'A borrowed question?',
                 'branches': [{'id': 'unknown', 'label': 'Unknown.', 'target': 'end'}]},
                {'id': 'end', 'kind': 'terminal', 'question': 'Done.'},
            ],
        })
