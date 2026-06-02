"""Interactive decision-tree node definitions (user-driven mode)."""

from __future__ import annotations

from advocate_bot_qualtrics.decision_tree.schemas import CurrentNode, TreeBranch


INTERACTIVE_START_NODE_ID = "confirm_last_payment"


INTERACTIVE_TREE: dict[str, CurrentNode] = {
    "confirm_last_payment": CurrentNode(
        node_id="confirm_last_payment",
        question="Do you see a specific last-payment date in the complaint facts?",
        branches=[
            TreeBranch(branch_id="yes", label="Yes, last-payment date is listed"),
            TreeBranch(branch_id="no", label="No, I do not see one"),
        ],
    ),
    "assignment_evidence": CurrentNode(
        node_id="assignment_evidence",
        question=(
            "Does the complaint include assignment or debt ownership evidence "
            "according to the extracted facts?"
        ),
        branches=[
            TreeBranch(branch_id="yes", label="Yes, assignment evidence exists"),
            TreeBranch(branch_id="no", label="No, assignment evidence is missing/unknown"),
        ],
    ),
    "review_questions": CurrentNode(
        node_id="review_questions",
        question="Any questions before we summarize next steps?",
        branches=[],
    ),
}
