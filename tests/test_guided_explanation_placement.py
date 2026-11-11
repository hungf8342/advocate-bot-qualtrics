"""Defense headings and explanation placement follow the screening structure."""
import pytest

from advocate_bot_qualtrics.practice_areas.consumer_debt.guided_debug import jump_to_section
from advocate_bot_qualtrics.practice_areas.consumer_debt.guided_sol import (
    CONTENT,DEFENSES,GuidedSolReview,GuidedAnswer,GuidedEditRequest,edit_review,
)
from test_guided_sol import review,advance_updated,both_defenses_history,answers


@pytest.mark.parametrize('choice',['yes','no'])
def test_mistake_general_explanation_and_checkbox_share_one_screen(choice):
    current=jump_to_section(GuidedSolReview(),'mistake')
    page=current.page()
    assert current.current=='mistake_decision'
    assert page['title']=='Mistake'
    assert page['body'][-1]=='Do you want to check off Mistake?'
    assert page['input_type']=='choice'
    assert [b['type'] for b in page['body_blocks']]==['paragraph','list','paragraph','paragraph']
    assert len(page['body_blocks'][1]['items'])==4
    assert page['answer_responses'][choice]==[]
    current=advance_updated(current,choice)
    assert current.current==DEFENSES['mistake']['summary']
    assert CONTENT['confirmation']['selected' if choice=='yes' else 'empty'] in current.page()['body']


def test_normal_traversal_goes_directly_from_ambiguity_review_to_mistake_question():
    history=both_defenses_history(complete=False)
    current=review(history+answers(('guided_ambiguity_summary','continue')))
    assert current.current=='mistake_decision'
    assert 'Mistake may apply' in ' '.join(current.page()['body'])
    current=advance_updated(current,'no')
    current=advance_updated(current,'continue')
    assert current.current=='guided_laches_intro'
    assert 'Laches may apply if:' in ' '.join(current.page()['body'])


def test_laches_explanation_has_its_own_page_before_screening():
    current=jump_to_section(GuidedSolReview(),'laches')
    assert current.current=='guided_laches_intro'
    assert current.page()['title']=='Laches'
    assert current.page()['input_type']=='continue'
    assert 'Laches may apply if:' in ' '.join(current.page()['body'])
    assert current.page()['body_blocks'][1]['type']=='list'
    current=advance_updated(current,'continue')
    assert current.current=='laches'
    assert current.page()['title']=='Are you locked out of your online portal?'
    assert 'Laches may apply if:' not in ' '.join(current.page()['body'])
    for answer in ['yes','no','no']:
        current=advance_updated(current,answer)
    assert current.current=='laches_decision'
    page=current.page()
    assert page['title']=='Do you want to check off Laches?'
    assert 'Laches may apply if:' not in ' '.join(page['body'])
    assert page['answer_responses']['yes']==[]
    current=advance_updated(current,'yes')
    assert current.current==DEFENSES['laches']['summary']
    assert CONTENT['confirmation']['selected'] in current.page()['body']


def test_laches_general_explanation_is_shown_even_if_no_checkbox_is_offered():
    current=jump_to_section(GuidedSolReview(),'laches')
    assert 'Laches may apply if:' in ' '.join(current.page()['body'])
    current=advance_updated(current,'continue')
    for answer in ['no','no','no']:
        current=advance_updated(current,answer)
    assert current.current=='laches_finish'
    current=advance_updated(current,'continue')
    assert current.current==DEFENSES['laches']['summary']
    assert current.page()['rows'][0]['status']=='Not offered on this path'


@pytest.mark.parametrize('defense,question',[('mistake','mistake_decision'),('laches','laches')])
def test_old_saved_intro_records_remain_replayable_and_editable(defense,question):
    fresh=jump_to_section(GuidedSolReview(),defense)
    history=fresh.history+[GuidedAnswer(node_id=DEFENSES[defense]['intro'],value='continue')]
    current=GuidedSolReview(debug_section=defense).replay(history)
    assert current.current==question
    assert current.page()['input_type']=='choice'
    index=next(i for i,a in enumerate(history) if a.node_id=='guided_plaintiff')
    current=edit_review({},GuidedEditRequest(history=history,debug_section=defense,edit_index=index,value='Changed Bank'))
    assert current.session.plaintiff_name=='Changed Bank'


def test_general_explanation_survives_mistake_uncertainty_retry():
    current=jump_to_section(GuidedSolReview(),'mistake')
    original=current.page()['body_blocks']
    current=advance_updated(current,'unknown')
    current=advance_updated(current,'retry')
    assert current.current=='mistake_decision'
    assert current.page()['body_blocks']==original


def test_old_completed_path_keeps_choices_after_an_unrelated_edit():
    history=both_defenses_history(complete=False)+answers(
        ('guided_ambiguity_summary','continue'),('guided_mistake_intro','continue'),
        ('mistake_decision','no'),('guided_mistake_summary','continue'),
        ('guided_laches_intro','continue'),('laches','yes'),('laches_statements','no'),
        ('laches_lost_info','no'),('laches_decision','yes'))
    current=review(history)
    assert current.current==DEFENSES['laches']['summary']
    index=next(i for i,a in enumerate(history) if a.node_id=='guided_plaintiff')
    current=edit_review({},GuidedEditRequest(history=history,edit_index=index,value='Corrected Bank'))
    for _ in range(8):
        if current.current==DEFENSES['laches']['summary']:
            break
        current=advance_updated(current,'continue')
    assert current.current==DEFENSES['laches']['summary']
    assert current.session.checkbox_selections['mistake']['main']=='exclude'
    assert current.session.checkbox_selections['laches']['main']=='include'


@pytest.mark.parametrize('defense', DEFENSES)
def test_every_defense_starts_with_its_name_as_the_heading(defense):
    current=jump_to_section(GuidedSolReview(),defense)
    from advocate_bot_qualtrics.practice_areas.consumer_debt.guided_sol import _screen_header
    assert current.page()['title']==(_screen_header(current.current,current.session) or DEFENSES[defense]['label'])


@pytest.mark.parametrize('defense',['ambiguity','mistake','unconscionable_contract'])
def test_defenses_without_screening_have_the_question_in_the_body(defense):
    current=jump_to_section(GuidedSolReview(),defense)
    page=current.page()
    assert page['input_type']=='choice'
    assert page['question_text']==f"Do you want to check off {DEFENSES[defense]['label']}?"
    assert page['body'][-1]==page['question_text']
    assert current.chat_node().question==page['question_text']


def test_saved_laches_path_without_intro_replays_and_edits():
    current=jump_to_section(GuidedSolReview(),'laches')
    history=current.history+answers(('laches','yes'),('laches_statements','no'),
                                    ('laches_lost_info','no'),('laches_decision','yes'))
    current=GuidedSolReview(debug_section='laches').replay(history)
    assert current.current==DEFENSES['laches']['summary']
    assert current.history==history
    index=next(i for i,a in enumerate(history) if a.node_id=='guided_plaintiff')
    current=edit_review({},GuidedEditRequest(history=history,debug_section='laches',edit_index=index,value='Changed Bank'))
    for _ in range(8):
        if current.current==DEFENSES['laches']['summary']:
            break
        current=advance_updated(current,'continue')
    assert current.current==DEFENSES['laches']['summary']
    assert current.session.checkbox_selections['laches']['main']=='include'
