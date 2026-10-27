"""Shared helpers for exercising the real engine without an external model."""
from dataclasses import replace

import pytest

from advocate_bot_qualtrics.core.bundle import get_bundle
from advocate_bot_qualtrics.core.engine import InteractiveChatEngine
from advocate_bot_qualtrics.core.schemas import ChatTurnResponse
from advocate_bot_qualtrics.practice_areas.consumer_debt.preliminary import PARSED_FIELDS
from advocate_bot_qualtrics.practice_areas.consumer_debt.session import apply_interactive_branch


@pytest.fixture
def scripted_engine(monkeypatch, tmp_path):
    from advocate_bot_qualtrics.core import engine as engine_module

    def chat(payload, node, facts, bundle):
        message = payload.rsplit('User: ', 1)[-1]
        definition = bundle.tree.node(node.node_id)
        branch = 'submit' if definition.input else message
        return ChatTurnResponse(user_intent='answer_node', assistant_reply='Recorded.',
                                next_node_id=branch, answer_confidence_pct=100)
    monkeypatch.setattr(engine_module, 'process_chat', chat)

    def make(node='statute_of_limitations_intro', **overrides):
        values = {'PLAINTIFF.TYPE': 'original', 'PLAINTIFF': 'Example Bank',
                  'ORIGINAL.CREDITOR': 'Example Original Bank', 'SUIT.TYPE': 'both',
                  'OWNERSHIP': True, 'OWNERSHIP.PROOF': True, 'STATEMENT': True,
                  'OPEN.DATE': '2020-01-01', 'LAST.PAYMENT.DATE': '2025-01-01',
                  'BREACH.DATE': '2025-02-01', 'COMPLAINT.DATE': '2026-01-01'}
        values.update(overrides)
        bundle = replace(get_bundle('consumer_debt'), get_session_fields_xlsx_path=lambda: tmp_path / 'fields.xlsx')
        engine = InteractiveChatEngine.from_user_input(bundle=bundle, complaint_fields=values)
        for _, verification in PARSED_FIELDS.values():
            apply_interactive_branch(engine.session, verification, 'yes')
        for n,b in [('prelim_recognize','yes'),('prelim_oral','no'),('prelim_consolidation','no')]:
            apply_interactive_branch(engine.session,n,b)
        engine.current_node_id = node
        return engine
    return make
