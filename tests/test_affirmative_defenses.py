"""AFF-01 document rules, date boundaries, and complete engine traversals."""

from datetime import date, timedelta

import pytest

from advocate_bot_qualtrics.core.engine import InteractiveChatEngine
from advocate_bot_qualtrics.core.schemas import ChatTurnResponse
from advocate_bot_qualtrics.practice_areas.consumer_debt.affirmative_defenses import (
    DEFENSE_LABELS,
    assess_defense,
    calendar_cutoff,
    defense_summary,
)
from advocate_bot_qualtrics.practice_areas.consumer_debt.host_extras import render_node
from advocate_bot_qualtrics.practice_areas.consumer_debt.session import InteractiveSessionState
from advocate_bot_qualtrics.practice_areas.consumer_debt.tree import INTERACTIVE_TREE_DEFINITION as TREE


def assess(defense, answers, **kwargs):
    session = InteractiveSessionState(defense_answers=answers, **kwargs)
    assess_defense(session, defense)
    return session.defense_results[defense]["status"]


@pytest.mark.parametrize("contract,state,years", [("oral", None, 2), ("written", "ca", 4), ("written", "de", 3)])
@pytest.mark.parametrize("offset,expected", [(-1, "checked"), (0, "unchecked"), (1, "unchecked")])
@pytest.mark.parametrize("creditor", ["original", "buyer"])
def test_sol_strict_filing_date_cutoff(contract, state, years, offset, expected, creditor):
    filing = date(2026, 9, 24)
    assert assess(
        "statute_of_limitations",
        {"sol_creditor_type": creditor, "sol_buyer_payment": "yes", "sol_contract": contract, "sol_state_law": state},
        filing_date=filing,
        **{("last_payment_debt_collector" if creditor == "buyer" else "last_payment_complaint"):
           calendar_cutoff(filing, years) + timedelta(days=offset)},
    ) == expected


def test_sol_leap_day_and_historical_filing():
    assert calendar_cutoff(date(2024, 2, 29), 3) == date(2021, 2, 28)
    # Even though this payment is old today, it was recent at filing.
    assert assess("statute_of_limitations", {"sol_creditor_type": "original"},
                  filing_date=date(2020, 1, 1), last_payment_complaint=date(2019, 1, 1)) == "unchecked"


def test_sol_debt_buyer_no_payment_preserves_without_dates():
    assert assess("statute_of_limitations", {"sol_creditor_type": "buyer", "sol_buyer_payment": "no"}) == "checked"


@pytest.mark.parametrize("state", ["other", "unknown"])
def test_written_contract_needs_clinic_confirmed_law(state):
    session = InteractiveSessionState(
        defense_answers={"sol_creditor_type": "original", "sol_contract": "written", "sol_state_law": state},
        filing_date=date(2026, 9, 24), last_payment_complaint=date(2010, 1, 1),
    )
    message = assess_defense(session, "statute_of_limitations")
    assert session.defense_results["statute_of_limitations"]["status"] == "unresolved"
    assert "Clinic staff must read" in message


@pytest.mark.parametrize("filing,payment", [(None, date(2020, 1, 1)), (date(2026, 1, 1), None), (date(2026, 1, 1), date(2026, 2, 1))])
def test_sol_missing_or_post_filing_dates_unresolved(filing, payment):
    assert assess("statute_of_limitations", {"sol_creditor_type": "original", "sol_contract": "oral"},
                  filing_date=filing, last_payment_complaint=payment) == "unresolved"


@pytest.mark.parametrize("defense,answers", [
    ("identity_theft", {"identity_recognize": "no", "identity_suspected": "yes"}),
    ("wrong_party", {"wrong_party_recognize": "no", "wrong_party_owner": "yes"}),
])
def test_referrals_stay_unresolved_and_continue(defense, answers):
    assert assess(defense, answers) == "unresolved"
    result = TREE.node(defense + "_result")
    assert result.kind == "action"
    assert result.next in TREE.node_map
    assert TREE.node(result.next).kind == "choice"


@pytest.mark.parametrize("defense,node", [("laches", "laches"), ("common_counts", "common_counts_reasons"), ("excuse_breach", "excuse_breach")])
@pytest.mark.parametrize("branch,status", [("yes", "checked"), ("no", "unchecked"), ("unknown", "unresolved")])
def test_any_of_subsections(defense, node, branch, status):
    assert assess(defense, {node: branch, "common_counts_claim": "yes"}) == status


def test_common_counts_only_for_common_count_claims():
    assert TREE.route("common_counts_claim", "yes") == "common_counts_reasons"
    assert TREE.route("common_counts_claim", "no") == "common_counts_result"
    assert TREE.route("common_counts_claim", "unknown") == "common_counts_result"
    assert assess("common_counts", {"common_counts_claim": "no"}) == "unchecked"
    assert assess("common_counts", {"common_counts_claim": "unknown"}) == "unresolved"


@pytest.mark.parametrize("contact,settlement,status,boxes", [
    ("unknown", "unknown", "checked", (True, False)),
    ("no", "no", "checked", (True, False)),
    ("yes", "unknown", "unchecked", (False, False)),
    ("yes", "yes", "checked", (False, True)),
])
def test_mitigation_nested_box_exceptions(contact, settlement, status, boxes):
    session = InteractiveSessionState(defense_answers={"mitigation_contact": contact, "mitigation_settlement": settlement})
    assess_defense(session, "failure_to_mitigate")
    assert session.defense_results["failure_to_mitigate"]["status"] == status
    assert tuple(session.mitigation_checkboxes.values()) == boxes


def test_consolidation_wording_carries_to_later_subsections():
    session = InteractiveSessionState(defense_answers={"mitigation_consolidation": "yes"})
    for node in ("mitigation_contact", "mitigation_settlement", "rescission", "accord_satisfaction"):
        assert "debt consolidation company" in render_node(node, None, session).question


def test_standing_and_cause_missing_information_and_unknowns():
    assert assess("standing_privity", {"standing_creditor_type": "buyer"}) == "checked"
    assert assess("standing_privity", {"standing_creditor_type": "original", "standing_claim": "yes", "standing_agreement": "unknown"}) == "unresolved"
    assert assess("standing_privity", {"standing_creditor_type": "original", "standing_claim": "no", "standing_agreement": "unknown"}) == "checked"
    answers = {"cause_creditor_type": "buyer", "cause_statement": "yes", "cause_purchase_claim": "yes", "cause_purchase_documents": "yes", "cause_breach_contract": "no"}
    assert assess("failure_to_state_cause", answers) == "unchecked"
    assert assess("failure_to_state_cause", {**answers, "cause_breach_contract": "unknown"}) == "unresolved"
    assert assess("failure_to_state_cause", {**answers, "cause_breach_contract": "yes", "cause_open_date": "no", "cause_breach_date": "unknown"}) == "checked"


@pytest.mark.parametrize("minor,incapacity,disclose,status", [
    ("no", "yes", "yes", "checked"), ("no", "yes", "no", "unchecked"),
    ("no", "yes", "unknown", "unresolved"), ("no", "no", "unknown", "unchecked"),
    ("yes", "unknown", "unknown", "checked"),
])
def test_capacity_requires_disclosure_consent_unless_minor(minor, incapacity, disclose, status):
    assert assess("capacity", {"capacity_minor": minor, "capacity_incapacitated": incapacity, "capacity_disclosure": disclose}) == status


@pytest.mark.parametrize("branches,status", [
    (("yes", "yes", "yes"), "checked"), (("yes", "yes", "no"), "unchecked"),
    (("yes", "unknown", "yes"), "unresolved"), (("no", "unknown", "yes"), "unchecked"),
])
def test_language_requires_all_three_conditions(branches, status):
    assert assess("language_1632", dict(zip(("language_primary", "language_negotiation", "language_contract"), branches))) == status


def test_graph_reachable_acyclic_and_every_path_finishes():
    seen = set()

    def visit(node_id, path):
        assert node_id not in path, f"Cycle: {path} -> {node_id}"
        if node_id in seen:
            return
        node = TREE.node(node_id)
        if node.kind == "terminal":
            assert node_id == "review_questions"
        else:
            targets = [b.target for b in node.branches] + ([node.next] if node.next else [])
            assert targets
            for target in targets:
                visit(target, path | {node_id})
        seen.add(node_id)

    visit(TREE.start_node_id, set())
    assert seen == set(TREE.node_map)
    assert [n.action.removeprefix("assess_") for n in TREE.nodes if n.kind == "action"] == list(DEFENSE_LABELS)
    assert all(TREE.route(n.id, "invalid") is None for n in TREE.nodes)


@pytest.mark.parametrize("default", ["yes", "no", "unknown"])
def test_automatic_traversal_finishes_with_checklist_and_open_questions(monkeypatch, tmp_path, default):
    """Exercise the real engine and hooks with a deterministic model substitute."""
    from advocate_bot_qualtrics.decision_tree import interactive_host

    def fake_chat(payload, node, facts, bundle):
        definition = bundle.tree.node(node.node_id)
        ids = {b.id for b in definition.branches}
        branch = default if default in ids else definition.idk_skip_branch_id
        if definition.kind == "input" and default != "unknown":
            branch = "submit"
        if node.node_id.endswith("creditor_type") and default != "unknown":
            branch = "original" if default == "yes" else "buyer"
        if node.node_id == "sol_contract" and default != "unknown":
            branch = "written" if default == "yes" else "oral"
        if node.node_id == "sol_state_law" and default != "unknown":
            branch = "ca"
        if node.node_id == "prelim_suit_type" and default != "unknown":
            branch = "both"
        assert branch in ids
        return ChatTurnResponse(user_intent="answer_node", assistant_reply="Recorded.", next_node_id=branch, answer_confidence_pct=100)

    monkeypatch.setattr(interactive_host, "process_chat", fake_chat)
    monkeypatch.setattr(interactive_host, "get_session_fields_xlsx_path", lambda: tmp_path / "fields.xlsx")
    engine = InteractiveChatEngine.from_user_input()
    visited = []
    for _ in range(len(TREE.nodes)):
        if engine.tree_complete:
            break
        node_id = engine.current_node_id
        visited.append(node_id)
        definition = TREE.node(node_id)
        message = default
        if definition.input and definition.input.type == "date":
            message = "2026-09-24" if node_id == "get_filing_date" else "2020-09-23"
        if default == "unknown":
            message = "I don't know"
        step = engine.submit(message)
        assert step.error is None
        assert step.branch_id in {b.id for b in TREE.node(node_id).branches}
    assert engine.tree_complete
    assert engine.current_node_id == "review_questions"
    assert list(engine.session.defense_results) == list(DEFENSE_LABELS)
    if default == "yes":
        assert "prelim_last_payment" in visited
        assert "get_last_payment_complaint" not in visited
        assert engine.session.filing_date == date(2026, 9, 24)
        assert engine.session.last_payment_complaint == date(2020, 9, 23)
        assert engine.session.defense_results["statute_of_limitations"]["status"] == "checked"
    summary = defense_summary(engine.session)
    assert "Defense checklist:" in summary
    assert "Open questions / clinic review:" in summary
    assert summary in engine.transcript[-1][1]
    assert "{defense_summary}" not in engine.transcript[-1][1]
    if default == "unknown":
        assert engine.session.defense_results["identity_theft"]["status"] == "unresolved"
        assert engine.session.defense_results["failure_to_mitigate"]["status"] == "checked"
