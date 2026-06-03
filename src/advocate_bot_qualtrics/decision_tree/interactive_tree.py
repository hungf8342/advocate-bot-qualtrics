"""Interactive decision-tree node definitions (user-driven mode)."""

from __future__ import annotations

from advocate_bot_qualtrics.decision_tree.schemas import CurrentNode, TreeBranch

# Template token filled at runtime from ComplaintFactSheet (see README).
_DATE_TOKEN = "{date_user_failed_to_pay}"

INTERACTIVE_START_NODE_ID = "confirm_last_payment"

# Only the SOL-related interactive path is mapped so far.
# Keys: (current_node_id, branch_id) -> next_node_id
INTERACTIVE_ROUTES: dict[tuple[str, str], str] = {
    ("confirm_last_payment", "yes"): "additional_payment_OG_owner",
    ("confirm_last_payment", "no"): "get_last_payment_date",
    ("additional_payment_OG_owner", "yes"): "get_last_payment_date",
    ("additional_payment_OG_owner", "no"): "additional_payment_buyer",
    ("additional_payment_buyer", "yes"): "get_last_payment_date",
    ("additional_payment_buyer", "no"): "threatening_arrest",
    ("get_last_payment_date", "submit"): "review_questions",
    ("get_last_payment_date", "no_date"): "review_questions",
    ("threatening_arrest", "yes"): "review_questions",
    ("threatening_arrest", "no"): "review_questions",
}


INTERACTIVE_TREE: dict[str, CurrentNode] = {
    "confirm_last_payment": CurrentNode(
        node_id="confirm_last_payment",
        question=f"Is {_DATE_TOKEN} the last payment date, according to the complaint?",
        branches=[
            TreeBranch(branch_id="yes", label="Yes, that is the last payment date."),
            TreeBranch(branch_id="no", label="No, the complaint lists a different date."),
        ],
    ),
    "additional_payment_OG_owner": CurrentNode(
        node_id="additional_payment_OG_owner",
        question=f"Did you make any payments to the original owner of the debt after {_DATE_TOKEN}?",
        branches=[
            TreeBranch(
                branch_id="yes",
                label=f"Yes, I made a payment to the original owner after {_DATE_TOKEN}.",
            ),
            TreeBranch(
                branch_id="no",
                label=f"No, I did not make any payments to the original owner after {_DATE_TOKEN}.",
            ),
        ],
    ),
    "additional_payment_buyer": CurrentNode(
        node_id="additional_payment_buyer",
        question=f"Did you make any payments to the debt buyer after {_DATE_TOKEN}?",
        branches=[
            TreeBranch(
                branch_id="yes",
                label=f"Yes, I made a payment to the debt buyer after {_DATE_TOKEN}.",
            ),
            TreeBranch(
                branch_id="no",
                label=f"No, I did not make any payments to the debt buyer after {_DATE_TOKEN}.",
            ),
        ],
    ),
    "get_last_payment_date": CurrentNode(
        node_id="get_last_payment_date",
        question="When did you last make a payment to the original company or debt buyer?",
        branches=[
            TreeBranch(
                branch_id="submit",
                label="The date submitted by the user, processed into YYYY-MM-DD format.",
            ),
            TreeBranch(branch_id="no_date", label="The user doesn't know the date."),
        ],
    ),
    "threatening_arrest": CurrentNode(
        node_id="threatening_arrest",
        question=(
            "Did the debt buyer threaten that you could be arrested for non-payment?"
        ),
        branches=[
            TreeBranch(
                branch_id="yes",
                label="Yes, the debt buyer threatened that I could be arrested for non-payment.",
            ),
            TreeBranch(
                branch_id="no",
                label="No, the debt buyer did not threaten that I could be arrested for non-payment.",
            ),
        ],
    ),
    "review_questions": CurrentNode(
        node_id="review_questions",
        question="Any questions before we summarize next steps?",
        branches=[],
    ),
}
