"""November 10 Word footnotes define user-visible screens for the 17 defenses."""
from copy import deepcopy
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile
import runpy

import pytest

from advocate_bot_qualtrics.practice_areas.consumer_debt.guided_debug import jump_to_section
from advocate_bot_qualtrics.practice_areas.consumer_debt.guided_script_formatting import SOURCE_FORMATTING
from advocate_bot_qualtrics.practice_areas.consumer_debt.guided_sol import (
    ACTION_SCREENS, COMPLETE, CONTENT, CONTINUE_PAGES, DEFENSES, EXTRA_SCREENS,
    INTRO_DEFENSES, PARENT_SCREENS, SCREEN_LAYOUT, SUMMARIES, TREE,
    GuidedAdvanceRequest, GuidedAnswer, GuidedSolReview, _screen_header, advance_review,
)
from test_guided_sol import intake

ROOT = Path(__file__).resolve().parents[1]


def start(defense, *, creditor='buyer', consolidation='no', suit='both', oral='no', payment='2024-03-15'):
    history = intake(creditor, oral=oral, payment=payment)[:-2]
    changes = {'guided_consolidation': consolidation, 'guided_suit_type': suit}
    history = [a.model_copy(update={'value': changes[a.node_id]}) if a.node_id in changes else a for a in history]
    return jump_to_section(GuidedSolReview().replay(history), defense)


def step(current, value='continue'):
    return advance_review(current.defaults, GuidedAdvanceRequest(
        history=current.history, revision=current.revision,
        debug_section=current.debug_section, value=value))


def begin(defense, **kwargs):
    current = start(defense, **kwargs)
    if current.current in INTRO_DEFENSES:
        current = step(current)
    return current


def test_screen_map_is_complete_and_headers_are_extracted_from_the_approved_word_document():
    source = ROOT / CONTENT['source']
    assert source.name == '2026.11.10 Affirmative-Defense-Scripts.docx'
    assert SCREEN_LAYOUT['source'] == CONTENT['source'] == SOURCE_FORMATTING['source']
    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    with ZipFile(source) as document:
        footnotes = ET.fromstring(document.read('word/footnotes.xml'))
    raw = {p.get('{'+ns['w']+'}id'): ''.join(t.text or '' for t in p.findall('.//w:t',ns)).strip().removeprefix('NEW SCREEN:').strip()
           for p in footnotes}
    assert raw == SOURCE_FORMATTING['screen_headers']
    used = {SCREEN_LAYOUT['clarification_footnote'], *SCREEN_LAYOUT['excluded_footnotes']}
    for node, spec in SCREEN_LAYOUT['headers'].items():
        assert node in TREE.node_map or node in INTRO_DEFENSES or node in EXTRA_SCREENS or node in PARENT_SCREENS
        used.add(spec['footnote'])
        used.update(v['footnote'] for v in spec.get('variants', []))
    assert used == set(raw)
    assert set(SCREEN_LAYOUT['excluded_footnotes']) == {'42'}
    module=runpy.run_path(str(ROOT/'scripts/extract_guided_script_formatting.py'))
    assert module['extract_prototype_formatting']() == SOURCE_FORMATTING


@pytest.mark.parametrize('defense', DEFENSES)
def test_every_defense_has_a_source_header_and_can_reach_its_own_review(defense):
    current = start(defense)
    for _ in range(60):
        before = deepcopy(current.__dict__)
        page = current.page()
        assert current.__dict__ == before
        header = _screen_header(current.current, current.session)
        if header:
            assert page['title'] == header
        if current.current == DEFENSES[defense]['summary']:
            assert page['rows'] and 'open_questions' in page
            assert page['body'] == [CONTENT['confirmation']['empty']]
            return
        value = 'continue' if current.current in CONTINUE_PAGES else 'English' if page['input_type']=='text' else 'no'
        current = step(current, value)
    pytest.fail(defense)


@pytest.mark.parametrize('defense,values,outcome,header', [
    ('laches',['no','no','no'],'laches_finish','Laches does not apply'),
    ('fraud',['no'],'fraud_finish','Fraud, Misrepresentation, and Concealment does not apply'),
    ('rescission',['no'],'rescission_no_request','Rescission does not apply'),
    ('rescission',['yes','no'],'rescission_granted','Rescission does not apply'),
    ('lack_of_consideration',['yes'],'consideration_used','Lack of Consideration does not apply'),
    ('lack_of_consideration',['no','yes'],'consideration_intended','Lack of Consideration does not apply'),
    ('accord_satisfaction',['no'],'accord_finish','Accord and Satisfaction does not apply'),
    ('waiver',['no'],'waiver_finish','Waiver does not apply'),
    ('oral_modification',['no'],'oral_modification_finish','Oral Modification does not apply'),
    ('tender_payment',['no'],'tender_payment_finish','Tender of Payment does not apply'),
])
def test_no_offer_results_have_their_own_screen_before_review(defense,values,outcome,header):
    current = begin(defense)
    for value in values:
        assert current.page()['answer_responses'][value] == []
        current = step(current,value)
    assert current.current == outcome
    page = current.page()
    assert page['title'] == header and page['input_type']=='continue'
    assert 'does not apply' in ' '.join(page['body']) or 'may not apply' in ' '.join(page['body'])
    assert current._current_defense() == defense
    with pytest.raises(ValueError,match='Choose Next'):
        step(current,'yes')
    current = step(current)
    assert current.current == DEFENSES[defense]['summary']
    assert current.page()['body'] == [CONTENT['confirmation']['empty']]


@pytest.mark.parametrize('consolidation',['yes','no'])
@pytest.mark.parametrize('contact,settlement',['yes yes'.split(),'no no'.split(),'yes no'.split(),'no yes'.split()])
def test_mitigation_guidance_and_parent_have_separate_screens(consolidation,contact,settlement):
    current = begin('failure_to_mitigate',consolidation=consolidation)
    assert ('debt consolidation company' in current.page()['title']) == (consolidation=='yes')
    assert current.current=='mitigation_settlement'
    current=step(current,settlement)
    assert current.current==('mitigation_first_checkbox' if settlement=='yes' else 'mitigation_first_no')
    current=step(current,'yes' if settlement=='yes' else 'continue')
    assert current.current=='mitigation_contact'
    current=step(current,contact)
    assert current.current==('mitigation_second_no' if contact=='yes' else 'mitigation_second_checkbox')
    current=step(current,'continue' if contact=='yes' else 'yes')
    assert current.current=='guided_failure_to_mitigate_parent'
    assert current.page()['title']=='Main Failure to Mitigate checkbox'
    assert current.page()['input_type']=='continue'
    assert current.session.checkbox_selections['failure_to_mitigate']['main']==('include' if settlement=='yes' or contact=='no' else 'exclude')
    current=step(current)
    assert current.current==DEFENSES['failure_to_mitigate']['summary']


@pytest.mark.parametrize('defense,values,parent', [
    ('common_counts',['yes','no','no'],'guided_common_counts_parent'),
    ('excuse_breach',['no','yes','no','no','no'],'guided_excuse_breach_parent'),
])
def test_other_derived_parent_checkboxes_get_source_information_screens(defense,values,parent):
    current=begin(defense)
    for value in values: current=step(current,value)
    assert current.current==parent
    assert 'main' not in [option['value'] for option in current.page().get('options',[])]
    assert current.session.checkbox_selections[defense]['main']=='include'
    assert 'Check off the overall' in ' '.join(current.page()['body'])
    current=step(current)
    assert current.current==DEFENSES[defense]['summary']


def test_capacity_opening_date_and_staff_referral_are_distinct_screens():
    current=begin('capacity')
    assert current.current=='guided_capacity_opening'
    assert current.page()['title']=='Account opening date'
    assert len(current.page()['body_blocks'])==2
    current=step(current)
    assert current.current=='capacity_minor'
    current=step(current,'no');current=step(current,'yes');current=step(current,'no')
    assert current.current=='capacity_staff_help'
    assert current.page()['title']=='Ask clinic staff for help'
    assert 'Please raise your hand' in ' '.join(current.page()['body'])
    assert step(current,'unknown').current=='capacity_staff_help'
    assert step(current,'resolved').current==DEFENSES['capacity']['summary']


@pytest.mark.parametrize('defense,node', [('fraud','fraud_hidden_facts'),('waiver','waiver_payment_without_penalty'),('oral_modification','oral_modification_agreement'),('tender_payment','tender_payment_refused')])
def test_shared_clarification_uses_source_header_and_next_returns_to_question(defense,node):
    current=begin(defense)
    assert current.current==node
    current=step(current,'unknown')
    assert current.page()['title']=='Ready to return to the pending question?'
    assert current.page()['input_type']=='continue'
    assert CONTENT['shared_clarification'] in current.page()['body']
    current=step(current)
    assert current.current==node
    assert current.session.defense_open_questions


@pytest.mark.parametrize('path',['yes','no'])
def test_full_traversal_reaches_all_seventeen_sections_and_final_review(path):
    current=start('statute_of_limitations',oral='yes')
    seen=set();visited=set()
    for _ in range(350):
        page=current.page();seen.add(current._current_defense());visited.add(current.current)
        if current.current==COMPLETE:break
        value='continue' if current.current in CONTINUE_PAGES else 'Spanish' if page['input_type']=='text' else path
        if current.current=='language_contract':value='no'
        current=step(current,value)
    assert current.current==COMPLETE
    assert seen==set(DEFENSES)
    assert len(current.page()['groups'])==17
    for defense, group in zip(DEFENSES, current.page()['groups'], strict=True):
        for row in group['rows'][1:]:
            assert row['label'] == CONTENT['summary_labels'][defense][row['id']]
            assert row['detail'] == 'Nested checkbox'
    if path=='yes':
        assert {'guided_capacity_opening','guided_oral_modification_change',*PARENT_SCREENS} <= visited
    assert not {'failure_to_mitigate_decision','common_counts_decision','excuse_breach_decision',
                'mitigation_contact_uncertain','mitigation_settlement_uncertain'} & visited


def test_uncertain_mitigation_contact_stays_unknown_after_shared_clarification():
    current=begin('failure_to_mitigate')
    for value in ['no','continue','unknown']:
        current=step(current,value)
    assert current.current=='mitigation_contact_help_help'
    assert current.page()['title']=='Ready to return to the pending question?'
    assert any(block['type']=='list' for block in current.page()['body_blocks'])
    current=step(current)
    assert current.current=='mitigation_contact_resolve'
    current=step(current,'unknown')
    assert current.current=='mitigation_second_checkbox'
    assert current.session.defense_answers['mitigation_contact']=='unknown'
    assert not current.session.checkbox_selections.get('failure_to_mitigate')
