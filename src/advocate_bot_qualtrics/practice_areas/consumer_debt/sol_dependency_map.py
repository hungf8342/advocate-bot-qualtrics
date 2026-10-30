"""Trace checkbox goals backward to their facts before editing a guided review.

Rules and dependency edges live in sol_checkbox_dependencies.yaml. Evaluation
short-circuits irrelevant facts: debt buyers do not depend on payment timing,
and an ineligible path does not need the oral-agreement answer.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field


class SolDependencyPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    affected_boxes: list[str] = Field(default_factory=list)
    availability: dict[str, bool | None]
    required_questions: list[str] = Field(default_factory=list)
    used_facts: list[str] = Field(default_factory=list)


@lru_cache(maxsize=1)
def load_dependency_map() -> dict:
    with Path(__file__).with_name("sol_checkbox_dependencies.yaml").open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    # Walk every goal at load time, rejecting missing facts/rules and cycles.
    for box in data["checkboxes"].values():
        _rule_facts(data, {"rule": box["rule"]})
    return data


def _rule_facts(data: dict, expression: dict, trail: tuple[str, ...] = ()) -> set[str]:
    if "fact" in expression:
        name = expression["fact"]
        if name not in data["facts"]:
            raise ValueError(f"Unknown SOL dependency fact: {name}")
        return {name}
    if "rule" in expression:
        name = expression["rule"]
        if name in trail or name not in data["rules"]:
            raise ValueError(f"Missing or cyclic SOL dependency rule: {name}")
        return _rule_facts(data, data["rules"][name], (*trail, name))
    operator = "all" if "all" in expression else "any"
    return set().union(*(_rule_facts(data, child, trail) for child in expression[operator]))


def affected_checkboxes(field_or_question: str) -> list[str]:
    data = load_dependency_map()
    if field_or_question in data["personalization_only"]:
        return []
    affected = []
    for key, box in data["checkboxes"].items():
        facts = _rule_facts(data, {"rule": box["rule"]})
        dependencies = {value for fact in facts for value in [*data["facts"][fact]["fields"], *data["facts"][fact]["questions"]]}
        if field_or_question in dependencies or field_or_question == box["question"]:
            affected.append(key)
    return affected


def plan_checkbox_review(
    facts: dict[str, str | None],
    fact_questions: dict[str, str],
    choices: dict[str, str],
    changed_field: str | None = None,
) -> SolDependencyPlan:
    data = load_dependency_map()
    used_facts = []

    def evaluate(expression: dict) -> tuple[bool | None, list[str]]:
        if "rule" in expression:
            return evaluate(data["rules"][expression["rule"]])
        if "fact" in expression:
            name = expression["fact"]
            used_facts.append(name)
            value = facts.get(name)
            if value is None:
                return None, [fact_questions[name]]
            return (value == expression["equals"] if "equals" in expression else value in expression["one_of"]), []
        if "all" in expression:
            for child in expression["all"]:
                result, questions = evaluate(child)
                if result is not True:
                    return result, questions
            return True, []
        pending = []
        for child in expression["any"]:
            result, questions = evaluate(child)
            if result is True:
                return True, []
            if result is None:
                pending.extend(questions)
        return (None, pending) if pending else (False, [])

    availability, required = {}, []
    for key, box in data["checkboxes"].items():
        available, questions = evaluate({"rule": box["rule"]})
        availability[key] = available
        required.extend(questions)
        if available and choices.get(key) not in {"yes", "no"}:
            required.append(box["question"])
    return SolDependencyPlan(affected_boxes=affected_checkboxes(changed_field) if changed_field else [],
                             availability=availability, required_questions=list(dict.fromkeys(required)),
                             used_facts=list(dict.fromkeys(used_facts)))
