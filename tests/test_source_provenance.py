"""V3 source provenance, new screen boundaries, and unchanged defense scope."""
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile
import hashlib
import runpy

import pytest

from advocate_bot_qualtrics.practice_areas.consumer_debt.workflow import (
    CONTENT, DEFENSE, SUMMARY,
)
from advocate_bot_qualtrics.practice_areas.consumer_debt.script_formatting import SOURCE_FORMATTING
from test_clickthrough_workflow import intake, review, advance_updated

ROOT = Path(__file__).resolve().parents[1]


def test_v3_is_the_current_source_and_matches_the_download():
    source = ROOT / CONTENT['source']
    assert source.name == '2026.11.10 Affirmative-Defense-Scripts.docx'
    assert CONTENT['sol_source'] == CONTENT['source'] == SOURCE_FORMATTING['source']
    assert hashlib.sha256(source.read_bytes()).hexdigest() == SOURCE_FORMATTING['source_sha256']
    module = runpy.run_path(str(ROOT / 'scripts/extract_script_formatting.py'))
    assert module['extract_prototype_formatting']() == SOURCE_FORMATTING


@pytest.mark.parametrize('creditor', ['original', 'buyer'])
@pytest.mark.parametrize('choice', ['yes', 'no'])
def test_written_contract_information_is_a_required_separate_screen(creditor, choice):
    current = review(intake(creditor))
    if creditor == 'original':
        current = advance_updated(current, 'yes')
    current = advance_updated(current, 'yes')
    assert current.current == 'sol_checkboxes_first_third'
    assert len(current.page()['body_blocks']) == 2
    assert current.page()['answer_responses'][choice] == []
    current = advance_updated(current, choice)
    assert current.current == 'sol_written'
    page = current.page()
    assert page['title'] == 'The second indented Statute of Limitations checkbox'
    assert page['input_type'] == 'continue'
    assert len(page['body_blocks']) == 2
    assert page['body_blocks'][0]['text'].startswith('You previously indicated your contract')
    assert page['body_blocks'][1]['text'] == 'The defense under the second indented checkbox does not apply.'
    assert 'Based on your answers' not in ' '.join(page['body'])
    current = advance_updated(current, 'continue')
    assert current.current == SUMMARY
    assert 'Based on your answers' in ' '.join(current.page()['body'])


def test_v3_oral_contract_guidance_keeps_all_three_paragraphs():
    current = review(intake('buyer', oral='yes'))
    for value in ('yes', 'yes'):
        current = advance_updated(current, value)
    assert current.current == 'sol_checkbox_second'
    blocks = current.page()['body_blocks']
    assert len(blocks) == 3
    assert blocks[0]['text'] == 'Oral contracts have shorter statute of limitations.'
    assert blocks[1]['text'].startswith('You’ve indicated your contract with Original Example Bank was oral.')
    assert blocks[2]['text'].startswith('People in this situation often check off')


def test_v3_payment_question_names_the_plaintiff_and_fixes_the_main_guidance():
    current = review(intake(payment='missing'))
    assert current.page()['body'] == ['Was your last payment to Example Bank after 2025-09-20?']
    current = advance_updated(current, 'no')
    text = ' '.join(current.page()['body'])
    assert 'was on or before 2025-09-20' in text
    assert 'was filed on or before' not in text
    details = {row['node_id']: row['value'] for row in current.case_details()}
    assert details['guided_filing_date'] == 'September 20, 2026'


def test_both_versions_other_defense_wording_is_identical():
    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    sections = []
    for version in ('v2', 'v3'):
        with ZipFile(ROOT / f'docs/source-material/2026-11-07/2026.11.07 Affirmative-Defense-Scripts-{version}.docx') as source:
            root = ET.fromstring(source.read('word/document.xml'))
        paragraphs = [''.join(t.text or '' for t in p.findall('.//w:t', ns)) for p in root.findall('.//w:p', ns)]
        boundary = max(i for i, text in enumerate(paragraphs) if text == '2 Ambiguity')
        sections.append(paragraphs[boundary:])
    assert sections[0] == sections[1]
