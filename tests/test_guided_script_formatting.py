"""Formatting is taken from the November 7 Word source, not inferred from prose."""
import hashlib
import runpy
from pathlib import Path

import pytest

from advocate_bot_qualtrics.practice_areas.consumer_debt.guided_script_formatting import (
    SOURCE_FORMATTING,ScriptFormatter,normalized,
)
from advocate_bot_qualtrics.practice_areas.consumer_debt.guided_sol import CONTENT,DEFENSES,GuidedSolReview
from advocate_bot_qualtrics.practice_areas.consumer_debt.guided_debug import jump_to_section
from advocate_bot_qualtrics.practice_areas.consumer_debt.host_extras import _script_text
from test_guided_november_scripts import reach,submit

ROOT=Path(__file__).resolve().parents[1]


def test_formatting_is_reproducibly_extracted_from_the_current_word_document():
    module=runpy.run_path(str(ROOT/'scripts/extract_guided_script_formatting.py'))
    source=ROOT/CONTENT['source']
    assert SOURCE_FORMATTING['source']==CONTENT['source']
    assert SOURCE_FORMATTING['source_sha256']==hashlib.sha256(source.read_bytes()).hexdigest()
    assert module['extract_prototype_formatting']()==SOURCE_FORMATTING
    sol_source=ROOT/CONTENT['sol_source']
    assert SOURCE_FORMATTING['sol_source_sha256']==hashlib.sha256(sol_source.read_bytes()).hexdigest()
    assert SOURCE_FORMATTING['screen_headers']


@pytest.mark.parametrize('defense',DEFENSES)
def test_each_defense_intro_uses_word_source_paragraphs(defense):
    current=jump_to_section(GuidedSolReview(),'preliminary')
    text=_script_text(CONTENT['nodes'][defense+'_intro']['explanation'],current.session)
    formatter=ScriptFormatter(current.session)
    for line in text.splitlines():
        if line.strip(): assert formatter.match(line) is not None,(defense,line)


def test_ambiguity_keeps_two_real_bullets_and_following_paragraphs():
    current=jump_to_section(GuidedSolReview(),'ambiguity')
    blocks=current.page()['body_blocks']
    assert [b['type'] for b in blocks]==['paragraph','list','paragraph','paragraph','paragraph']
    assert blocks[0]['text'].endswith('confused about:')
    assert [i['text'] for i in blocks[1]['items']]==['the complaint; or','the amount of money you are being sued for']
    assert blocks[2]['text'].startswith('The documents filed with the court')
    assert blocks[3]['text']=='Many people check off ambiguity, since it is a broad defense.'
    assert blocks[4]['text']=='Do you want to check off Ambiguity?'
    assert any(b['type']=='list' for b in current.page()['help_blocks'])


def test_sol_preserves_its_deliberate_two_paragraph_general_explanation():
    current=jump_to_section(GuidedSolReview(),'statute_of_limitations')
    blocks=current.page()['body_blocks']
    assert [b['type'] for b in blocks]==['paragraph','paragraph']
    assert blocks[0]['text'].endswith('Statute of limitations is a strong defense if it applies.')
    assert blocks[1]['text'].startswith('Even if Example Harbor Bank sued within the time limit')


def test_capacity_preserves_two_separate_lists():
    current=jump_to_section(GuidedSolReview(),'capacity')
    blocks=current.page()['body_blocks']
    assert [b['type'] for b in blocks[:4]]==['paragraph','list','paragraph','list']
    assert len(blocks)==4
    opening=submit(current,'continue').page()['body_blocks']
    assert [b['type'] for b in opening]==['paragraph','paragraph']
    assert opening[0]['text'].startswith('According to the complaint')
    assert opening[1]['text'].startswith('If that date is incorrect')
    assert len(blocks[1]['items'])==2
    assert len(blocks[3]['items'])==1
    assert blocks[2]['text']=='Before sharing information about a mental condition:'


def test_laches_and_tender_screens_preserve_source_lists():
    current=submit(reach('laches'),'no','no')
    blocks=submit(current,'yes').page()['body_blocks']
    assert [b['type'] for b in blocks]==['paragraph','list','paragraph']
    assert len(blocks[1]['items'])==3
    current=reach('tender_payment')
    blocks=submit(current,'unknown').page()['body_blocks']
    lists=[b for b in blocks if b['type']=='list']
    assert len(lists)==1 and len(lists[0]['items'])==4


def test_overview_preserves_two_source_paragraphs():
    blocks=GuidedSolReview().page()['body_blocks']
    assert len(blocks)==2
    assert normalized(blocks[1]['text'])==normalized(CONTENT['overview'][1])


def test_reviewer_outline_bullets_do_not_turn_whole_quoted_replies_into_lists():
    formatter=ScriptFormatter(GuidedSolReview().session)
    assert formatter.blocks([CONTENT['confirmation']['selected']])==[
        {'type':'paragraph','text':CONTENT['confirmation']['selected']}]


def test_source_lists_in_a_question_are_not_flattened_into_the_heading():
    current=submit(reach('failure_to_mitigate'),'no','continue','unknown')
    page=current.page()
    assert page['title']=='Ready to return to the pending question?'
    assert page['body_blocks'][-1]['type']=='list'
    assert len(page['body_blocks'][-1]['items'])==3


def test_identity_related_fraud_response_uses_november_7_wording_and_paragraphs():
    text=CONTENT['nodes']['fraud_identity_yes']['question']
    assert 'without your permission' in text
    assert 'You said earlier' in text
    formatter=ScriptFormatter(GuidedSolReview().session)
    blocks=formatter.blocks([text])
    assert len(blocks)==2
    assert all(formatter.match(block['text']) is not None for block in blocks)
