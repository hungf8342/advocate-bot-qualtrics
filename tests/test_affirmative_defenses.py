"""Deterministic October 25 conditions, unknown facts, and date boundaries."""
from collections import deque
from datetime import date, timedelta
from itertools import product
import pytest

from advocate_bot_qualtrics.practice_areas.consumer_debt.affirmative_defenses import calendar_cutoff,script_condition
from advocate_bot_qualtrics.practice_areas.consumer_debt.tree import INTERACTIVE_TREE_DEFINITION as TREE


@pytest.mark.parametrize('offset,expected',[(-1,'yes'),(0,'yes'),(1,'no')])
def test_sol_inclusive_one_calendar_year_cutoff(offset,expected,scripted_engine):
    filing=date(2026,9,24);payment=calendar_cutoff(filing,1)+timedelta(days=offset)
    e=scripted_engine(**{'COMPLAINT.DATE':filing.isoformat(),'LAST.PAYMENT.DATE':payment.isoformat()})
    assert script_condition(e.session,'rule:agreed_payment_age')==expected


def test_calendar_cutoff_handles_leap_day():
    assert calendar_cutoff(date(2024,2,29),1)==date(2023,2,28)


@pytest.mark.parametrize('filing,payment',[(None,'2020-01-01'),('2026-01-01',None),('2026-01-01','2026-02-01')])
def test_unusable_dates_never_become_a_negative_screen(filing,payment,scripted_engine):
    e=scripted_engine(**{'COMPLAINT.DATE':filing,'LAST.PAYMENT.DATE':payment})
    assert script_condition(e.session,'rule:agreed_payment_age')=='unknown'


@pytest.mark.parametrize('contact,settlement,expected',[(a,b,'yes' if a=='no' or b=='yes' else 'no' if a=='yes' and b=='no' else 'unknown') for a,b in product(['yes','no','unknown'],repeat=2)])
def test_mitigation_uses_script_conditions(contact,settlement,expected,scripted_engine):
    e=scripted_engine();e.session.defense_answers.update(mitigation_contact=contact,mitigation_settlement=settlement)
    assert script_condition(e.session,'rule:mitigation')==expected


@pytest.mark.parametrize('values,expected',[(('yes','unknown','no'),'yes'),(('no','no','no'),'no'),(('no','unknown','no'),'unknown')])
def test_laches_aggregation_preserves_unknown(values,expected,scripted_engine):
    e=scripted_engine();e.session.defense_answers.update(zip(['laches','laches_statements','laches_lost_info'],values))
    assert script_condition(e.session,'rule:laches')==expected


@pytest.mark.parametrize('key',['field:PLAINTIFF','complaint:OWNERSHIP','complaint:OPEN-DATE','complaint:BREACH-DATE'])
def test_unverified_input_remains_unknown(key,scripted_engine):
    from advocate_bot_qualtrics.practice_areas.consumer_debt.session import init_session
    s=init_session({'PLAINTIFF.TYPE':'original','OWNERSHIP':False,'OPEN.DATE':None,'BREACH.DATE':None})
    assert script_condition(s,key)=='unknown'


def test_every_declared_rule_and_wording_condition_has_a_binding(scripted_engine):
    e=scripted_engine()
    for n in TREE.nodes:
        if n.condition_key:
            branch=script_condition(e.session,n.condition_key)
            assert branch in {b.id for b in n.branches},(n.id,branch)
        for variant in [*n.question_variants,*n.fact_restatements]:
            assert isinstance(script_condition(e.session,variant.fact_key),str)


def test_every_node_is_reachable_and_can_reach_terminal():
    forward={n.id:[b.target for b in n.branches]+([n.next] if n.next else []) for n in TREE.nodes}
    reverse={n:[] for n in forward}
    for node,targets in forward.items():
        for target in targets:reverse[target].append(node)
    def reachable(graph,start):
        reached=set();pending=deque([start])
        while pending:
            node=pending.popleft()
            if node in reached:continue
            reached.add(node);pending.extend(graph[node])
        return reached
    assert reachable(forward,TREE.start_node_id)==set(forward)
    assert reachable(reverse,'review_questions')==set(forward)
