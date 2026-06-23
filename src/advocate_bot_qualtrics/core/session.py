"""Generic session helpers shared across practice areas."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class NodeAnswerRecord:
    branch_id: str
    confidence_pct: int
    skipped: bool = False


def record_node_answer(
    session: object,
    node_id: str,
    branch_id: str,
    confidence_pct: int,
    *,
    skipped: bool = False,
) -> None:
    """Store branch choice and confidence for a completed tree node."""
    session.node_answers[node_id] = NodeAnswerRecord(
        branch_id=branch_id,
        confidence_pct=confidence_pct,
        skipped=skipped,
    )
