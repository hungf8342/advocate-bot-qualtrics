from collections import deque
from datetime import date

from advocate_bot_qualtrics.decision_tree.interactive_session import (
    InteractiveSessionState,
    advance_from_hook,
    apply_interactive_branch,
    init_session_from_fact_sheet,
    is_interactive_hook_node,
)
from advocate_bot_qualtrics.decision_tree.interactive_tree import (
    INTERACTIVE_CONDITIONAL_ROUTE_NODES,
    INTERACTIVE_HOOK_ADVANCES,
    INTERACTIVE_HOOK_NODE_IDS,
    INTERACTIVE_ROUTES,
    INTERACTIVE_START_NODE_ID,
    INTERACTIVE_TREE,
    resolve_interactive_next_node,
)
from advocate_bot_qualtrics.schemas.complaint_fact_sheet import ComplaintFactSheet


def test_every_non_terminal_node_has_static_or_conditional_route():
    missing: list[str] = []
    for node_id, node in INTERACTIVE_TREE.items():
        if not node.branches or node_id in INTERACTIVE_HOOK_NODE_IDS:
            continue
        for branch in node.branches:
            if node_id in INTERACTIVE_CONDITIONAL_ROUTE_NODES:
                assert resolve_interactive_next_node(node_id, branch.branch_id) is not None
                continue
            if (node_id, branch.branch_id) not in INTERACTIVE_ROUTES:
                missing.append(f"{node_id}:{branch.branch_id}")
    assert not missing, f"Missing routes: {missing}"


def test_every_route_target_exists_in_tree():
    invalid = [
        f"({node_id}, {branch_id}) -> {target}"
        for (node_id, branch_id), target in INTERACTIVE_ROUTES.items()
        if target not in INTERACTIVE_TREE
    ]
    assert not invalid, f"Invalid route targets: {invalid}"


def test_hook_advances_point_to_valid_nodes():
    invalid = [
        f"{hook} -> {target}"
        for hook, target in INTERACTIVE_HOOK_ADVANCES.items()
        if target not in INTERACTIVE_TREE
    ]
    assert not invalid, f"Invalid hook advances: {invalid}"


def test_terminal_node_has_no_outgoing_routes():
    outgoing = [key for key in INTERACTIVE_ROUTES if key[0] == "review_questions"]
    assert outgoing == []


def test_all_nodes_reachable_from_start():
    profiles = [
        InteractiveSessionState(threatened=True),
        InteractiveSessionState(),
    ]
    reachable: set[str] = set()
    for session in profiles:
        queue: deque[tuple[str, InteractiveSessionState | None]] = deque(
            [(INTERACTIVE_START_NODE_ID, session)]
        )
        while queue:
            node_id, sess = queue.popleft()
            if node_id in reachable:
                continue
            reachable.add(node_id)
            if node_id in INTERACTIVE_HOOK_NODE_IDS:
                hook_next = advance_from_hook(node_id)
                if hook_next:
                    queue.append((hook_next, sess))
                continue
            node = INTERACTIVE_TREE[node_id]
            for branch in node.branches:
                next_id = resolve_interactive_next_node(node_id, branch.branch_id, sess)
                if next_id is None:
                    next_id = INTERACTIVE_ROUTES.get((node_id, branch.branch_id))
                if next_id:
                    queue.append((next_id, sess))

    assert reachable == set(INTERACTIVE_TREE.keys())


def test_resolve_skips_evidence_when_no_fdcpa_flags():
    session = InteractiveSessionState()
    apply_interactive_branch(session, "threatening_arrest", "no")
    apply_interactive_branch(session, "contact_third_parties", "no")
    assert resolve_interactive_next_node("contact_third_parties", "no", session) == (
        "fdcpa_computation"
    )


def test_resolve_routes_to_evidence_when_threatened():
    session = InteractiveSessionState()
    apply_interactive_branch(session, "threatening_arrest", "yes")
    assert resolve_interactive_next_node("contact_third_parties", "no", session) == (
        "record_bad_behavior"
    )


def test_apply_interactive_branch_stores_dates_and_flags():
    session = InteractiveSessionState()
    apply_interactive_branch(
        session,
        "get_last_payment_OG_creditor",
        "submit",
        submitted_date=date(2021, 1, 15),
    )
    apply_interactive_branch(session, "threatening_arrest", "yes")
    assert session.last_payment_og_creditor == date(2021, 1, 15)
    assert session.threatened is True
    assert session.disclosed is False


def test_init_session_from_fact_sheet():
    facts = ComplaintFactSheet(
        date_complaint_filed=date(2025, 9, 30),
        date_user_failed_to_pay=date(2020, 12, 23),
    )
    session = init_session_from_fact_sheet(facts)
    assert session.filing_date == date(2025, 9, 30)
    assert session.last_payment_complaint == date(2020, 12, 23)


def test_is_interactive_hook_node():
    assert is_interactive_hook_node("sol_computation")
    assert is_interactive_hook_node("fdcpa_computation")
    assert not is_interactive_hook_node("threatening_arrest")


def test_advance_from_hook():
    assert advance_from_hook("sol_computation") == "threatening_arrest"
    assert advance_from_hook("fdcpa_computation") == "review_questions"
    assert advance_from_hook("unknown") is None
