"""October source integration, personalized routing, and clinic-review behavior."""

from datetime import date
from itertools import product
from pathlib import Path
from zipfile import ZipFile
import xml.etree.ElementTree as ET

import pytest

from advocate_bot_qualtrics.core.engine import InteractiveChatEngine
from advocate_bot_qualtrics.core.schemas import ChatTurnResponse
from advocate_bot_qualtrics.practice_areas.consumer_debt.affirmative_defenses import (
    DEFENSE_LABELS, assess_defense, complaint_payment,
)
from advocate_bot_qualtrics.practice_areas.consumer_debt.host_extras import render_node, skip_collected_date_node
from advocate_bot_qualtrics.practice_areas.consumer_debt.session import apply_interactive_branch, init_session
from advocate_bot_qualtrics.practice_areas.consumer_debt.tree import INTERACTIVE_TREE_DEFINITION as TREE

FIRST_NINE = list(DEFENSE_LABELS)[:9]


def confirmed_session(**overrides):
    values = {
        "PLAINTIFF": "Example Buyer", "ORIGINAL.CREDITOR": "Example Bank",
        "PLAINTIFF.TYPE": "buyer", "COMPLAINT.DATE": "2026-10-01",
        "LAST.PAYMENT.DATE": "2025-10-01", "OPEN.DATE": "2020-01-01",
        "SUIT.TYPE": "both", "STATEMENT": True, "OWNERSHIP": True,
        "OWNERSHIP.PROOF": False,
    }
    values.update(overrides)
    session = init_session(values)
    from advocate_bot_qualtrics.practice_areas.consumer_debt.preliminary import PARSED_FIELDS
    for external in values:
        apply_interactive_branch(session, PARSED_FIELDS[external][1], "yes")
    return session


def test_all_nine_general_explanations_match_current_word_document():
    path = Path(__file__).resolve().parents[1] / 'docs/source-material/2026-10-11/2026.10.11 explanations-aff-defenses.docx'
    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    with ZipFile(path) as doc:
        root = ET.fromstring(doc.read('word/document.xml'))
    paragraphs = [''.join(t.text or '' for t in p.findall('.//w:t', ns)).strip()
                  for p in root.findall('.//w:p', ns)]
    explanations = []
    for i, text in enumerate(paragraphs):
        if text == 'General Explanation':
            explanations.append(next(p for p in paragraphs[i + 1:] if p))
    assert len(explanations) == 9
    assert [TREE.node(key + '_intro').explanation.text for key in FIRST_NINE] == explanations


def test_headings_general_facts_and_application_are_in_order_even_when_facts_reused():
    engine = InteractiveChatEngine.from_user_input()
    engine.session = confirmed_session()
    apply_interactive_branch(engine.session, 'prelim_recognize', 'yes')
    engine.current_node_id = 'standing_privity_intro'
    text = '\n\n'.join(engine._drain_hooks())
    assert text.index('### Standing/privity') < text.index('To sue for your debt') < text.index('Compared to original creditors')
    assert text.count('### Standing/privity') == 1
    assert engine.current_node_id == 'standing_privity_decision'
    engine._append_transcript('user', 'Yes, check it off.')
    engine.current_node_id = 'failure_to_state_cause_intro'
    text = '\n\n'.join(engine._drain_hooks())
    assert text.index('### Failure to State a Cause of Action') < text.index('attaching proof') < text.index('The complaint states') < text.index('Debt buyers must attach') < text.index('This defense may not apply')
    assert text.count('### Failure to State a Cause of Action') == 1
    assert 'Example Buyer' in text and 'Example Bank' in text
    assert '[PLAINTIFF]' not in text and '{defense_facts}' not in text
    assert 'Result:' not in text and 'Personalized Application' not in text
    assert engine.current_node_id == 'failure_to_state_cause_decision'


@pytest.mark.parametrize('statement,proof,breach,open_present,payment_present', list(product([True, False], repeat=5)))
def test_buyer_cause_alternative_attachments_and_breach_dates(statement, proof, breach, open_present, payment_present):
    session = confirmed_session(**{
        'STATEMENT': statement, 'OWNERSHIP.PROOF': proof,
        'SUIT.TYPE': 'both' if breach else 'common',
        'OPEN.DATE': '2020-01-01' if open_present else None,
        'LAST.PAYMENT.DATE': '2025-10-01' if payment_present else None,
    })
    skip_collected_date_node('cause_creditor_type', session)
    assess_defense(session, 'failure_to_state_cause')
    expected = (not statement and not proof) or (breach and (not open_present or not payment_present))
    assert session.defense_results['failure_to_state_cause']['status'] == ('checked' if expected else 'unchecked')


def test_original_cause_uses_attached_proof_not_ownership_assertion():
    session = confirmed_session(**{'PLAINTIFF.TYPE': 'original', 'OWNERSHIP': True, 'OWNERSHIP.PROOF': False})
    skip_collected_date_node('cause_creditor_type', session)
    assess_defense(session, 'failure_to_state_cause')
    assert session.defense_results['failure_to_state_cause']['status'] == 'checked'
    assert 'documents supporting ownership' in session.defense_results['failure_to_state_cause']['reason']
    skip_collected_date_node('standing_creditor_type', session)
    assess_defense(session, 'standing_privity')
    assert session.defense_results['standing_privity']['status'] == 'unchecked'


def test_payment_estimate_does_not_replace_scraped_date_or_complaint_presence():
    session = confirmed_session(**{'PLAINTIFF.TYPE': 'original', 'LAST.PAYMENT.DATE': '2020-01-01'})
    assert skip_collected_date_node('sol_creditor_type', session) == 'sol_payment_estimate_agree'
    apply_interactive_branch(session, 'sol_payment_estimate_agree', 'no')
    apply_interactive_branch(session, 'sol_payment_age', 'yes')
    assess_defense(session, 'statute_of_limitations')
    assert session.defense_results['statute_of_limitations']['status'] == 'unchecked'
    assert complaint_payment(session) == date(2020, 1, 1)
    assert session.preliminary_fields['LAST-PAYMENT-DATE'].parsed_value == date(2020, 1, 1)
    assert session.preliminary_fields['LAST-PAYMENT-DATE'].complaint_status == 'present'


@pytest.mark.parametrize('recognize,suspect,expected_node', [
    ('yes', None, 'fraud_hidden_facts'), ('no', 'yes', 'fraud_result'),
    ('no', 'no', 'fraud_hidden_facts'), ('no', 'unknown', 'fraud_hidden_facts'),
    ('unknown', None, 'fraud_hidden_facts'),
])
def test_fraud_reuses_identity_suspicion_and_handles_skipped_question(recognize, suspect, expected_node):
    session = confirmed_session()
    apply_interactive_branch(session, 'prelim_recognize', recognize)
    session.defense_answers['identity_recognize'] = recognize
    if suspect:
        session.defense_answers['identity_suspected'] = suspect
    assert skip_collected_date_node('fraud_identity', session) == expected_node
    if suspect == 'yes':
        assess_defense(session, 'fraud')
        assert session.defense_results['fraud']['status'] == 'checked'


@pytest.mark.parametrize('defense,node,prefix', [
    ('identity_theft', 'identity_help', 'identity'), ('wrong_party', 'wrong_party_help', 'wrong_party'),
])
@pytest.mark.parametrize('recognition', ['no', 'unknown'])
def test_uncertainty_offers_help_and_keeps_review_open(monkeypatch, defense, node, prefix, recognition):
    from advocate_bot_qualtrics.core import engine as engine_module
    monkeypatch.setattr(engine_module, 'process_chat', lambda *args: ChatTurnResponse(
        user_intent='answer_node', assistant_reply='Recorded.', next_node_id='yes', answer_confidence_pct=100))
    engine = InteractiveChatEngine.from_user_input()
    engine.session = confirmed_session()
    engine.session.defense_answers[prefix + '_recognize'] = recognition
    engine.session.defense_answers['identity_suspected' if defense == 'identity_theft' else 'wrong_party_owner'] = 'unknown'
    engine.current_node_id = node
    step = engine.submit('Yes, please help')
    assert step.error is None
    result = engine.session.defense_results[defense]
    assert result['status'] == 'unresolved'
    assert 'raise your hand' in result['reason']
    assert step.current_node_id != node
    assert 'you’re responsible' not in result['reason']


@pytest.mark.parametrize('answers,status', [
    (('no', 'no', 'no'), 'unchecked'), (('yes', 'no', 'no'), 'checked'),
    (('no', 'yes', 'no'), 'checked'), (('no', 'no', 'yes'), 'checked'),
    (('no', 'unknown', 'no'), 'unresolved'), (('yes', 'unknown', 'no'), 'checked'),
])
def test_laches_three_questions_aggregate_without_reversing_statement_answer(answers, status):
    session = init_session()
    session.defense_answers.update(zip(('laches', 'laches_statements', 'laches_lost_info'), answers))
    assess_defense(session, 'laches')
    assert session.defense_results['laches']['status'] == status


def test_debt_buyer_statement_definition_contains_charge_off_date_in_document_order():
    prompt = render_node('verify_statement', None, confirmed_session()).question
    assert prompt.index('final balance') < prompt.index('charge-off date') < prompt.index('Look through the pages') < prompt.index('Do you agree')
    original = render_node('verify_statement', None, confirmed_session(**{'PLAINTIFF.TYPE': 'original'})).question
    assert 'charge-off date' not in original


def test_missing_buyer_attachments_skip_unnecessary_date_questions():
    session = confirmed_session(**{'STATEMENT': False, 'OWNERSHIP.PROOF': False})
    assert skip_collected_date_node('cause_creditor_type', session) == 'failure_to_state_cause_result'
    assert 'cause_breach_contract' not in session.defense_answers
    assert 'cause_open_date' not in session.defense_answers


def test_payment_intake_uses_complaint_definition_and_defers_uncertainty():
    session = confirmed_session(**{'LAST.PAYMENT.DATE': None})
    prompt = render_node('verify_last_payment', None, session).question
    assert 'does not appear to list the last payment date' in prompt
    assert 'An estimated year' not in prompt
    assert '{complaint_payment_restatement}' not in prompt
    apply_interactive_branch(session, 'prelim_creditor_type', 'original')
    assert skip_collected_date_node('sol_creditor_type', session) == 'sol_payment_age'
    assert 'The complaint did not appear to include' in render_node('sol_payment_age', None, session).question


def test_defense_help_uses_document_explanation_without_advancing(monkeypatch):
    from advocate_bot_qualtrics.core import engine as engine_module
    monkeypatch.setattr(engine_module, 'process_chat', lambda *args: ChatTurnResponse(
        user_intent='ask_about_complaint', assistant_reply='Concealment means hiding important information that should have been disclosed.'))
    engine = InteractiveChatEngine.from_user_input()
    engine.session = confirmed_session()
    engine.current_node_id = 'fraud_hidden_facts'
    step = engine.submit('What does concealment mean?')
    assert step.error is None
    assert step.current_node_id == 'fraud_hidden_facts'
    assert 'Concealment means hiding important information' in step.assistant_messages[0]
    assert 'Model paraphrase' not in step.assistant_messages[0]
    assert 'Example Buyer or Example Bank' in step.assistant_messages[-1]
