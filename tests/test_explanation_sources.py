"""The October 25 scripts govern defenses; preliminary text keeps its prior source."""
from pathlib import Path
from zipfile import ZipFile
import xml.etree.ElementTree as ET
import pytest
from pydantic import ValidationError

from advocate_bot_qualtrics.core.tree_definition import TreeDefinition
from advocate_bot_qualtrics.practice_areas.consumer_debt.affirmative_defenses import DOCUMENTED_DEFENSES
from advocate_bot_qualtrics.practice_areas.consumer_debt.tree import INTERACTIVE_TREE_DEFINITION as TREE

ROOT=Path(__file__).resolve().parents[1]


def paragraphs(path):
    with ZipFile(path) as doc:root=ET.fromstring(doc.read('word/document.xml'))
    ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    return [''.join(t.text or '' for t in p.findall('.//w:t',ns)).strip() for p in root.findall('.//w:p',ns)]


def test_all_21_defense_explanations_are_exact_source_quotations():
    source=paragraphs(ROOT/'docs/source-material/2026-10-25/2026.10.25 Affirmative-Defense-Scripts.docx')
    actual=[n for n in TREE.nodes if n.id.endswith('_intro')]
    assert [n.id.removesuffix('_intro') for n in actual]==list(DOCUMENTED_DEFENSES)
    for n in actual:
        assert '“'+n.explanation.text+'”' in source
        assert n.explanation.show_with_question
    assert not any(n.action and n.action.startswith('assess_') for n in TREE.nodes)


def test_question_variants_and_fact_restatements_are_approved_source_text():
    source=paragraphs(ROOT/'docs/source-material/2026-10-25/2026.10.25 Affirmative-Defense-Scripts.docx')
    quotes={p[1:-1] for p in source if p.startswith('“') and p.endswith('”')}
    for n in TREE.nodes:
        for variant in n.question_variants:
            assert variant.text.split('\n\nDo you want to check off ',1)[0] in quotes
        for fact in n.fact_restatements:assert fact.text in quotes


def test_preliminary_explanations_keep_their_source_except_new_breach_date_field():
    approved=set(paragraphs(ROOT/'docs/source-material/2026-10-11/2026.10.11 explanations-prelim-questions.docx'))
    for n in TREE.nodes:
        if n.discussion_topic or n.id=='verify_breach_date' or not n.explanation:continue
        for text in [b.text for b in n.explanation.blocks] or [n.explanation.text]:assert text in approved


@pytest.mark.parametrize('defense',['ambiguity','mistake','unconscionable_contract'])
def test_general_only_defenses_have_no_added_fact_quiz(defense,scripted_engine):
    e=scripted_engine(defense+'_intro');messages=e._drain_hooks()
    assert e.current_node_id==defense+'_decision'
    assert len(messages)==1 and TREE.node(defense+'_intro').explanation.text in messages[0]
    assert not e.session.checkbox_selections


def test_each_condition_is_automatic_and_declares_an_uncertainty_path(scripted_engine):
    e=scripted_engine()
    for n in TREE.nodes:
        if n.kind!='condition':continue
        assert n.question=='' and n.explanation is None
        assert 'unknown' in {b.id for b in n.branches}
        if n.discussion_topic:assert n.condition_key


def test_condition_schema_rejects_a_user_question():
    with pytest.raises(ValidationError,match='cannot ask a question'):
        TreeDefinition.model_validate({'id':'bad','version':'1','start_node_id':'gate','nodes':[
            {'id':'gate','kind':'condition','question':'A question?','branches':[{'id':'unknown','label':'Unknown','target':'end'}]},
            {'id':'end','kind':'terminal','question':'Done.'}]})


def test_every_script_quotation_is_represented_in_the_active_tree():
    source=paragraphs(ROOT/'docs/source-material/2026-10-25/2026.10.25 Affirmative-Defense-Scripts.docx')
    texts=str(TREE.model_dump())
    template='“Do you want to check off [name or description of this defense]?”'
    for p in source:
        if p.startswith('“') and p.endswith('”') and p!=template:
            assert p[1:-1] in texts,p
