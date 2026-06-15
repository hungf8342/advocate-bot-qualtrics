"""Interactive decision-tree node definitions (user-driven mode)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from advocate_bot_qualtrics.decision_tree.schemas import CurrentNode, TreeBranch

if TYPE_CHECKING:
    from advocate_bot_qualtrics.decision_tree.interactive_session import InteractiveSessionState

_FILING_DATE_TOKEN = "{date_complaint_filed}"
_LAST_PAYMENT_COMPLAINT_TOKEN = "{date_user_failed_to_pay}"

INTERACTIVE_START_NODE_ID = "confirm_filing_date"

INTERACTIVE_HOOK_NODE_IDS: frozenset[str] = frozenset(
    {"sol_computation", "fdcpa_computation"}
)

# Keys: (current_node_id, branch_id) -> next_node_id
# contact_third_parties routing is conditional; see resolve_interactive_next_node.
INTERACTIVE_ROUTES: dict[tuple[str, str], str] = {
    ("confirm_filing_date", "yes"): "confirm_last_payment_complaint",
    ("confirm_filing_date", "no"): "different_complaint_filing",
    ("different_complaint_filing", "yes"): "confirm_filing_date",
    ("different_complaint_filing", "no"): "get_filing_date",
    ("get_filing_date", "submit"): "confirm_last_payment_complaint",
    ("get_filing_date", "no_date"): "confirm_last_payment_complaint",
    ("confirm_last_payment_complaint", "yes"): "additional_payment_OG_creditor",
    ("confirm_last_payment_complaint", "no"): "different_complaint_last_payment",
    ("different_complaint_last_payment", "yes"): "confirm_filing_date",
    ("different_complaint_last_payment", "no"): "get_last_payment_complaint",
    ("get_last_payment_complaint", "submit"): "additional_payment_OG_creditor",
    ("get_last_payment_complaint", "no_date"): "additional_payment_OG_creditor",
    ("additional_payment_OG_creditor", "yes"): "get_last_payment_OG_creditor",
    ("additional_payment_OG_creditor", "no"): "additional_payment_debt_collector",
    ("get_last_payment_OG_creditor", "submit"): "additional_payment_debt_collector",
    ("get_last_payment_OG_creditor", "no_date"): "additional_payment_debt_collector",
    ("additional_payment_debt_collector", "yes"): "get_last_payment_debt_collector",
    ("additional_payment_debt_collector", "no"): "sol_computation",
    ("get_last_payment_debt_collector", "submit"): "sol_computation",
    ("get_last_payment_debt_collector", "no_date"): "sol_computation",
    ("threatening_arrest", "yes"): "contact_third_parties",
    ("threatening_arrest", "no"): "contact_third_parties",
    ("record_bad_behavior", "yes"): "fdcpa_computation",
    ("record_bad_behavior", "no"): "fdcpa_computation",
}

INTERACTIVE_HOOK_ADVANCES: dict[str, str] = {
    "sol_computation": "threatening_arrest",
    "fdcpa_computation": "review_questions",
}

INTERACTIVE_CONDITIONAL_ROUTE_NODES: frozenset[str] = frozenset({"contact_third_parties"})

# Host skip branch when user gives pure "I don't know" (no yes/no lean).
INTERACTIVE_IDK_SKIP_BRANCH: dict[str, str] = {
    "confirm_filing_date": "yes",
    "confirm_last_payment_complaint": "yes",
    "get_filing_date": "no_date",
    "get_last_payment_complaint": "no_date",
    "get_last_payment_OG_creditor": "no_date",
    "get_last_payment_debt_collector": "no_date",
    "different_complaint_filing": "no",
    "different_complaint_last_payment": "no",
    "additional_payment_OG_creditor": "no",
    "additional_payment_debt_collector": "no",
    "threatening_arrest": "no",
    "contact_third_parties": "no",
    "record_bad_behavior": "no",
}


def idk_skip_branch_for_node(node_id: str) -> str | None:
    return INTERACTIVE_IDK_SKIP_BRANCH.get(node_id)


def resolve_interactive_next_node(
    current_node_id: str,
    branch_id: str,
    session: InteractiveSessionState | None = None,
) -> str | None:
    """Map a node's branch_id (from process_chat next_node_id) to the next node id."""
    if current_node_id == "contact_third_parties":
        if session is not None and not session.threatened and not session.disclosed:
            return "fdcpa_computation"
        return "record_bad_behavior"
    return INTERACTIVE_ROUTES.get((current_node_id, branch_id))


INTERACTIVE_TREE: dict[str, CurrentNode] = {
    "confirm_filing_date": CurrentNode(
        node_id="confirm_filing_date",
        question=f"Is the filing date of the complaint {_FILING_DATE_TOKEN}?",
        branches=[
            TreeBranch(branch_id="yes", label="Yes, that is the filing date."),
            TreeBranch(
                branch_id="no",
                label="No, that is not the filing date shown in the complaint.",
            ),
        ],
    ),
    "different_complaint_filing": CurrentNode(
        node_id="different_complaint_filing",
        question="Are you possibly looking at a different complaint?",
        branches=[
            TreeBranch(
                branch_id="yes",
                label="Yes, I may be looking at a different complaint.",
            ),
            TreeBranch(
                branch_id="no",
                label="No, this is the same complaint; the filing date is wrong.",
            ),
        ],
    ),
    "get_filing_date": CurrentNode(
        node_id="get_filing_date",
        question="What is the correct filing date of the complaint?",
        branches=[
            TreeBranch(
                branch_id="submit",
                label="The filing date submitted by the user, in YYYY-MM-DD format.",
            ),
            TreeBranch(branch_id="no_date", label="I don't know the filing date."),
        ],
    ),
    "confirm_last_payment_complaint": CurrentNode(
        node_id="confirm_last_payment_complaint",
        question=(
            f"Is the last time you made a compliant payment to the original creditor "
            f"{_LAST_PAYMENT_COMPLAINT_TOKEN}?"
        ),
        branches=[
            TreeBranch(branch_id="yes", label="Yes, that is the last payment date."),
            TreeBranch(
                branch_id="no",
                label="No, that is not the last payment date shown in the complaint.",
            ),
        ],
    ),
    "different_complaint_last_payment": CurrentNode(
        node_id="different_complaint_last_payment",
        question="Are you possibly looking at a different complaint?",
        branches=[
            TreeBranch(
                branch_id="yes",
                label="Yes, I may be looking at a different complaint.",
            ),
            TreeBranch(
                branch_id="no",
                label="No, this is the same complaint; the last payment date is wrong.",
            ),
        ],
    ),
    "get_last_payment_complaint": CurrentNode(
        node_id="get_last_payment_complaint",
        question="What is the correct last payment date per your records?",
        branches=[
            TreeBranch(
                branch_id="submit",
                label="The last payment date submitted by the user, in YYYY-MM-DD format.",
            ),
            TreeBranch(branch_id="no_date", label="I don't know the last payment date."),
        ],
    ),
    "additional_payment_OG_creditor": CurrentNode(
        node_id="additional_payment_OG_creditor",
        question="Did you make additional payments afterwards to the original creditor?",
        branches=[
            TreeBranch(
                branch_id="yes",
                label="Yes, I made additional payments to the original creditor.",
            ),
            TreeBranch(
                branch_id="no",
                label="No, I did not make additional payments to the original creditor.",
            ),
        ],
    ),
    "get_last_payment_OG_creditor": CurrentNode(
        node_id="get_last_payment_OG_creditor",
        question="When did you make the last additional payment to the original creditor?",
        branches=[
            TreeBranch(
                branch_id="submit",
                label="The date submitted by the user, in YYYY-MM-DD format.",
            ),
            TreeBranch(branch_id="no_date", label="I don't know the date."),
        ],
    ),
    "additional_payment_debt_collector": CurrentNode(
        node_id="additional_payment_debt_collector",
        question="Did you make additional payments afterwards to the debt collector?",
        branches=[
            TreeBranch(
                branch_id="yes",
                label="Yes, I made additional payments to the debt collector.",
            ),
            TreeBranch(
                branch_id="no",
                label="No, I did not make additional payments to the debt collector.",
            ),
        ],
    ),
    "get_last_payment_debt_collector": CurrentNode(
        node_id="get_last_payment_debt_collector",
        question="When did you make the last additional payment to the debt collector?",
        branches=[
            TreeBranch(
                branch_id="submit",
                label="The date submitted by the user, in YYYY-MM-DD format.",
            ),
            TreeBranch(branch_id="no_date", label="I don't know the date."),
        ],
    ),
    "sol_computation": CurrentNode(
        node_id="sol_computation",
        question=(
            "Computing statute of limitations: compare the complaint filing date to "
            "the most recent payment date (complaint, original creditor, or debt collector) "
            "and check whether more than 3 years have passed."
        ),
        branches=[],
    ),
    "threatening_arrest": CurrentNode(
        node_id="threatening_arrest",
        question=(
            "Did the debt collector threaten that you could be arrested for not paying your debt?"
        ),
        branches=[
            TreeBranch(
                branch_id="yes",
                label="Yes, the debt collector threatened that I could be arrested.",
            ),
            TreeBranch(
                branch_id="no",
                label="No, the debt collector did not threaten arrest.",
            ),
        ],
    ),
    "contact_third_parties": CurrentNode(
        node_id="contact_third_parties",
        question=(
            "Did the debt collector disclose your debt to third parties like your family "
            "or friends without your permission?"
        ),
        branches=[
            TreeBranch(
                branch_id="yes",
                label="Yes, the debt collector disclosed my debt to a third party.",
            ),
            TreeBranch(
                branch_id="no",
                label="No, the debt collector did not disclose my debt to third parties.",
            ),
        ],
    ),
    "record_bad_behavior": CurrentNode(
        node_id="record_bad_behavior",
        question=(
            "Do you have written or recorded evidence of the debt collector's bad behavior?"
        ),
        branches=[
            TreeBranch(
                branch_id="yes",
                label="Yes, I have written or recorded evidence.",
            ),
            TreeBranch(
                branch_id="no",
                label="No, I do not have written or recorded evidence.",
            ),
        ],
    ),
    "fdcpa_computation": CurrentNode(
        node_id="fdcpa_computation",
        question=(
            "Computing FDCPA defense strength from arrest threats, third-party disclosures, "
            "and whether written or recorded evidence exists."
        ),
        branches=[],
    ),
    "review_questions": CurrentNode(
        node_id="review_questions",
        question="Any questions before we summarize next steps?",
        branches=[],
    ),
}
