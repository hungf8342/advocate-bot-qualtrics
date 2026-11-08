"""A page-oriented adapter for the implemented affirmative-defense scripts.

Each request replays a valid answer path into a fresh session. Edits reconcile
previous answers against the new path, retaining only applicable choices.
This adapter never submits chat messages as answers or enters excluded defenses.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from advocate_bot_qualtrics.core.schemas import CurrentNode, NodeExplanation
from .guided_script_formatting import ScriptFormatter
from advocate_bot_qualtrics.core.tree_definition import TreeDefinition
from advocate_bot_qualtrics.practice_areas.consumer_debt.affirmative_defenses import calendar_cutoff, run_script_action, script_condition, script_fact
from advocate_bot_qualtrics.practice_areas.consumer_debt.host_extras import _script_text
from advocate_bot_qualtrics.practice_areas.consumer_debt.session import apply_interactive_branch, init_session
from advocate_bot_qualtrics.practice_areas.consumer_debt.tree import INTERACTIVE_TREE_DEFINITION as CHAT_TREE
from advocate_bot_qualtrics.practice_areas.consumer_debt.sol_dependency_map import SolDependencyPlan, load_dependency_map, plan_checkbox_review

DEFENSE = "statute_of_limitations"
SUMMARY = "guided_sol_summary"
AMBIGUITY_SUMMARY = "guided_ambiguity_summary"
LACHES_SUMMARY = "guided_laches_summary"
COMPLETE = "guided_sol_complete"
PRELIMINARY_SUMMARY = "guided_preliminary_summary"
SOL_INTRO = "guided_sol_intro"
LACHES_INTRO = "guided_laches_intro"
DEFENSES = {
    DEFENSE: {"label": "Statute of Limitations", "number": 1, "summary": SUMMARY, "intro": SOL_INTRO},
    "ambiguity": {"label": "Ambiguity", "number": 2, "summary": AMBIGUITY_SUMMARY},
}
for _number, _key, _label in [
    (5, "mistake", "Mistake"), (8, "laches", "Laches"),
    (9, "fraud", "Fraud Misrepresentation and Concealment"),
    (10, "failure_to_mitigate", "Failure to Mitigate"), (11, "common_counts", "Common Counts Only"),
    (12, "unconscionable_contract", "Unconscionable Contract"), (13, "rescission", "Rescission"),
    (14, "lack_of_consideration", "Lack of Consideration"), (15, "accord_satisfaction", "Accord and Satisfaction"),
    (16, "excuse_breach", "Excuse or Breach of Contract"), (17, "capacity", "Capacity"),
    (18, "waiver", "Waiver"), (19, "oral_modification", "Oral Modification"),
    (20, "tender_payment", "Tender of Payment"),
    (21, "language_1632", "Violation of Civil Code Section 1632 Regarding Language"),
]:
    DEFENSES[_key] = {"label": _label, "number": _number, "summary": "guided_" + _key + "_summary",
                      "intro": "guided_" + _key + "_intro"}
SUMMARIES = {spec["summary"] for spec in DEFENSES.values()}
INTRO_DEFENSES = {spec["intro"]: key for key, spec in DEFENSES.items() if "intro" in spec}
SUMMARY_DEFENSES = {spec["summary"]: key for key, spec in DEFENSES.items()}
CONTINUE_PAGES = {*SUMMARIES, PRELIMINARY_SUMMARY, *INTRO_DEFENSES, "guided_welcome"}
with Path(__file__).with_name("guided_defense_content.yaml").open(encoding="utf-8") as _content_file:
    CONTENT = yaml.safe_load(_content_file)
with Path(__file__).with_name("guided_preliminary_fields.yaml").open(encoding="utf-8") as _preliminary_file:
    PRELIMINARY = yaml.safe_load(_preliminary_file)
PRELIMINARY_FIELDS = PRELIMINARY["fields"]
YES_NO = [
    {"value": "yes", "label": "Yes"},
    {"value": "no", "label": "No"},
    {"value": "unknown", "label": "I’m not sure"},
]
BOX_LABELS = {
    "main": ("Statute of Limitations", "Main checkbox"),
    "first": ("California · written contract", "First indented checkbox"),
    "second": ("California · oral contract", "Second indented checkbox"),
    "third": ("Delaware", "Third indented checkbox"),
}
AMBIGUITY_BOX_LABELS = {"main": ("Ambiguity", "Main checkbox")}


def _prototype_tree() -> TreeDefinition:
    """Validate source-specific patches while leaving the chatbot tree intact."""
    data = CHAT_TREE.model_dump()
    data["version"] = "2026.11.07"
    for node in data["nodes"]:
        patch = CONTENT["nodes"].get(node["id"], {})
        for field, value in patch.items():
            if field == "explanation":
                node["explanation"]["text"] = value
            elif field == "routes":
                for branch in node["branches"]:
                    branch["target"] = value.get(branch["id"], branch["target"])
            else:
                node[field] = value
    return TreeDefinition.model_validate(data)


TREE = _prototype_tree()
PRESENTATION = CONTENT["presentation"]
FEEDBACK_BOX_LABELS = {key: {"main": spec["label"]} for key, spec in DEFENSES.items()}
for _node in TREE.nodes:
    for _box in _node.selection_checkboxes:
        if _box.defense_id in FEEDBACK_BOX_LABELS:
            FEEDBACK_BOX_LABELS[_box.defense_id].setdefault(_box.checkbox_id, _box.label)
PARENT_FROM_NESTED = {"failure_to_mitigate", "common_counts", "excuse_breach"}


def _condition(session, key):
    if key.startswith("selection:"):
        choices = session.checkbox_selections.get(key.split(":", 1)[1], {})
        return "yes" if any(v == "include" for v in choices.values()) else "no"
    return script_condition(session, key)


def render_node(node_id, facts, session):
    """Render November 7 wording for pages and clarification context alike."""
    definition = TREE.node(node_id)
    defense = next(key for key, spec in DEFENSES.items() if spec["label"] == definition.discussion_topic)

    def wording(node):
        text = next((v.text for v in node.question_variants
                     if _condition(session, v.fact_key) == v.equals), node.question)
        restatements = [v.text for v in node.fact_restatements
                        if _condition(session, v.fact_key) == v.equals]
        return _script_text("\n\n".join(part for part in [*restatements, text] if part), session)

    intro = TREE.node(defense + "_intro")
    approved = _script_text(intro.explanation.text, session)
    question = wording(definition)
    if node_id == defense + "_confirm":
        selected = any(v == "include" for v in session.checkbox_selections.get(defense, {}).values())
        question = CONTENT["confirmation"]["selected" if selected else "empty"]
    if definition.explanation and definition.explanation.show_with_question:
        question = approved + ("\n\n" + question if question else "")
    context = [approved]
    for visited in dict.fromkeys(session.script_visited):
        node = TREE.node(visited)
        if node.discussion_topic == definition.discussion_topic:
            context.append(wording(node))
    for node in TREE.nodes:
        if node.discussion_topic != definition.discussion_topic:
            continue
        answer = session.defense_answers.get(node.id)
        branch = next((b for b in node.branches if b.id == answer), None)
        if branch and node.kind in {"choice", "input"}:
            context.append(wording(node) + "\nRecorded answer: " + branch.label)
    context.append(question)
    return definition.to_current_node().model_copy(update={
        "question": f"### {definition.title}\n\n{question}",
        "explanation": NodeExplanation(text="\n\n".join(dict.fromkeys(part for part in context if part)))})


def _node_wording(node_id: str, session) -> str:
    node = TREE.node(node_id)
    text = next((v.text for v in node.question_variants
                 if _condition(session, v.fact_key) == v.equals), node.question)
    return _script_text(text, session)


def _response_prefix(node_id: str, session) -> tuple[str, str]:
    text = _node_wording(node_id, session)
    separator = PRESENTATION["prefix_separators"].get(node_id)
    if separator and separator in text:
        before, after = text.split(separator, 1)
        return before + ".", separator[2:] + after
    return "", text


class TimingBasis(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["comparison", "estimate"]
    filing_date: date | None
    payment_date: date | None = None


class GuidedAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    node_id: str = Field(min_length=1, max_length=100)
    value: str = Field(min_length=1, max_length=300)
    automatic: bool = False
    timing_basis: TimingBasis | None = None


class SavedAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer: GuidedAnswer
    payment_date: date | None = None
    filing_date: date | None = None


class GuidedRevision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    previous_history: list[GuidedAnswer] = Field(max_length=400)
    saved_answers: list[SavedAnswer] = Field(default_factory=list, max_length=400)
    changed_field: str | None = None
    plan: SolDependencyPlan | None = None


class GuidedRequest(BaseModel):
    debug_section: str | None = Field(default=None, min_length=1, max_length=100)
    model_config = ConfigDict(extra="forbid")
    history: list[GuidedAnswer] = Field(default_factory=list, max_length=400)
    revision: GuidedRevision | None = None


class GuidedEditRequest(GuidedRequest):
    edit_index: int = Field(ge=0, lt=400)
    value: str = Field(min_length=1, max_length=300)


class GuidedAdvanceRequest(GuidedRequest):
    value: str = Field(min_length=1, max_length=300)


class GuidedSolReview:
    def __init__(self, defaults: dict[str, Any] | None = None, *, debug_section: str | None = None):
        if debug_section is not None and debug_section not in {*DEFENSES, "preliminary"}:
            raise ValueError("Choose an implemented defense or preliminary fields.")
        self.debug_section = debug_section
        # Validate imported facts using the same fact-only contract as chat.
        init_session(defaults or {})
        self.defaults = defaults or {}
        self.session = init_session()
        self.current = "guided_welcome"
        self.history: list[GuidedAnswer] = []
        self.notices: list[str] = []
        self.answer_response: list[str] = []
        self.response_origin: str | None = None
        self.moved_preamble: str | None = None
        self.checkbox_context: dict[str, list[str]] = {}
        self.finish_reasons: dict[str, str] = {}
        self.revision: GuidedRevision | None = None
        self.pending_preliminary_route: str | None = None
        self.calculations: dict[str, str] = {}

    def replay(self, history: list[GuidedAnswer]) -> GuidedSolReview:
        for answer in history:
            self._restore_separate_intro(answer)
            if answer.node_id != self.current and not self._legacy_intro(answer):
                raise ValueError("These answers no longer match the current path. Return to the previous page.")
            self._apply_answer(answer)
            self.history.append(answer)
        return self

    def _restore_separate_intro(self, answer: GuidedAnswer) -> None:
        # A previous presentation briefly omitted the Laches introduction.
        # Replay those answers without changing their saved edit indices.
        if self.current == LACHES_INTRO and answer.node_id == TREE.node("laches_intro").next:
            self._apply_answer(GuidedAnswer(node_id=LACHES_INTRO, value="continue", automatic=True))

    def _legacy_intro(self, answer: GuidedAnswer) -> bool:
        defense = INTRO_DEFENSES.get(answer.node_id)
        return (defense in PRESENTATION["explanation_on_question"] and answer.value == "continue"
                and self.current == TREE.node(defense + "_intro").next)

    def _start_defense(self, defense: str) -> None:
        if defense in PRESENTATION["explanation_on_question"] or "intro" not in DEFENSES[defense]:
            self._drain(defense + "_intro")
        else:
            self.current = DEFENSES[defense]["intro"]

    def _apply_answer(self, answer: GuidedAnswer) -> None:
        if self._legacy_intro(answer):
            # Older saved paths included an extra introduction page. Its Continue
            # remains a harmless navigation record, not a new checkbox answer.
            return
        self.response_origin = self.current if self.current not in {*CONTINUE_PAGES, COMPLETE} else None
        self.answer_response = []
        self.moved_preamble = None
        self._apply_answer_value(answer)
        if self.response_origin is not None or self._checkbox_context_demo():
            self._finish_answer_response(answer.value)

    def _apply_answer_value(self, answer: GuidedAnswer) -> None:
        if answer.timing_basis is None:
            if answer.value in {"reuse_comparison", "reuse_estimate"}:
                raise ValueError("A retained timing result needs its original context.")
            self._answer(answer.value)
            return
        # Reusing a screening result must not record agreement with a new date.
        if self.current != "sol_payment_estimate_agree" or not answer.automatic:
            raise ValueError("This timing result cannot be reused on this page.")
        basis = answer.timing_basis
        if basis.kind == "estimate" and answer.value == "reuse_estimate":
            if basis.filing_date != self.session.filing_date:
                raise ValueError("The payment estimate needs review against the new filing date.")
            self.notices = []
            self._drain("sol_payment_age")
            return
        if basis.kind != "comparison" or answer.value != "reuse_comparison":
            raise ValueError("Invalid retained timing result.")
        before = _timing_result(basis.payment_date, basis.filing_date)
        after = _timing_result(_payment_date(self), self.session.filing_date)
        if before is None or after is None or before != after:
            raise ValueError("The updated dates need a new timing review.")
        self.notices = ["The updated dates give the same one-year screening result. Your previous checkbox choices can be retained."]
        self._drain("sol_original_preserve" if after else "sol_finish")

    def _checkbox_context_demo(self) -> bool:
        definition = TREE.node_map.get(self.current)
        return bool(definition and any(box.defense_id in PRESENTATION["checkbox_context_defenses"]
                                       for box in definition.selection_checkboxes))

    def _finish_answer_response(self, value: str) -> None:
        if self._checkbox_context_demo():
            # Keep checkbox guidance here; acknowledgments of the preceding
            # answer remain inline on the screening question that produced them.
            context = list(dict.fromkeys(self.notices))
            if context:
                self.checkbox_context[self.current] = context
            self.notices = list(self.checkbox_context.get(self.current, []))
            return
        rule = PRESENTATION["answer_rules"].get(self.response_origin, {}).get(value)
        if rule:
            node_id, part = rule["node"], rule["part"]
            text = _node_wording(node_id, self.session)
            if part == "preamble":
                text = text.rsplit("\n\n", 1)[0]
            elif part == "prefix":
                text = _response_prefix(node_id, self.session)[0]
            self.answer_response.insert(0, text)
        definition = TREE.node_map.get(self.current)
        if definition:
            oral_answer = self.current == "sol_checkbox_second" and self.response_origin == "guided_oral"
            if (definition.selection_checkboxes and (oral_answer or self.current not in
                    {*PRESENTATION["context_preambles"], *PRESENTATION["response_only_preambles"]})):
                text = _node_wording(self.current, self.session)
                if "\n\n" in text:
                    self.answer_response.append(text.rsplit("\n\n", 1)[0])
                    self.moved_preamble = self.current
            prefix, _ = _response_prefix(self.current, self.session)
            if prefix and self.current not in {"mitigation_contact_uncertain", "mitigation_settlement_uncertain"}:
                self.answer_response.append(prefix)
                self.moved_preamble = self.current
            if self.current == "language_negotiation":
                self.answer_response.extend(_script_text(v.text, self.session) for v in definition.fact_restatements
                                            if _condition(self.session, v.fact_key) == v.equals)
                self.moved_preamble = self.current
        self.answer_response = list(dict.fromkeys(text for text in self.answer_response if text.strip()))

    def preview_response(self, value: str) -> list[str]:
        """Evaluate one draft answer on a disposable copy; never collect or advance it."""
        preview = deepcopy(self)
        preview._apply_answer(GuidedAnswer(node_id=preview.current, value=value))
        return preview.answer_response

    def preview_formatted_response(self, value: str) -> dict:
        preview = deepcopy(self)
        preview._apply_answer(GuidedAnswer(node_id=preview.current, value=value))
        return {"response": preview.answer_response,
                "response_blocks": ScriptFormatter(preview.session).blocks(preview.answer_response)}

    def _answer(self, value: str) -> None:
        node = self.current
        if node == COMPLETE:
            raise ValueError("This section is already complete.")
        if node in CONTINUE_PAGES:
            if value != "continue":
                raise ValueError("Choose Next to continue.")
            self.notices = []
            if node in SUMMARY_DEFENSES:
                defense = SUMMARY_DEFENSES[node]
                if defense not in self.finish_reasons and defense + "_completed" in TREE.node_map:
                    run_script_action(self.session, "script_confirm:" + defense)
                order = list(DEFENSES)
                index = order.index(defense) + 1
                if index == len(order):
                    self.current = COMPLETE
                else:
                    following = order[index]
                    self._start_defense(following)
            elif node == PRELIMINARY_SUMMARY:
                target = self.debug_section if self.debug_section in DEFENSES else DEFENSE
                self._start_defense(target)
            elif node in INTRO_DEFENSES:
                self._drain(INTRO_DEFENSES[node] + "_intro")
            else:
                self.current = next(iter(PRELIMINARY_FIELDS))
            return
        if node.startswith("guided_"):
            self._intake(node, value)
            return
        definition = TREE.node(node)
        if definition.kind == "input":
            if value == "unknown":
                branch = "unknown"
                submitted = None
            else:
                branch = "submit"
                submitted = value
            apply_interactive_branch(self.session, node, branch, submitted_text=submitted)
        else:
            if value not in {b.id for b in definition.branches}:
                raise ValueError("Choose one of the answers shown on this page.")
            branch = value
            apply_interactive_branch(self.session, node, value)
        self.notices = []
        self._drain(TREE.route(node, branch))

    def _intake(self, node: str, value: str, *, advance: bool = True) -> None:
        spec = PRELIMINARY_FIELDS.get(node)
        if spec is None:
            raise ValueError("This page is not a preliminary field.")
        kind, binding = spec["input_type"], spec["binding"]
        if kind == "choice":
            if value not in {option["value"] for option in spec["options"]}:
                raise ValueError("Choose one of the answers shown on this page.")
            apply_interactive_branch(self.session, binding, value)
        elif kind == "date":
            alternatives = {"unknown", "missing"} if spec["allow_missing"] else {"unknown"}
            parsed = None
            if value not in alternatives:
                try:
                    parsed = date.fromisoformat(value)
                except ValueError as exc:
                    raise ValueError("Enter a real date in YYYY-MM-DD format, or choose an available alternative.") from exc
                if parsed.isoformat() != value:
                    raise ValueError("Use YYYY-MM-DD for the date.")
            apply_interactive_branch(self.session, binding, "submit" if parsed else value, submitted_date=parsed)
        else:
            if not value.strip():
                raise ValueError("Enter an answer to continue.")
            if kind == "currency" and value != "unknown":
                try:
                    amount = Decimal(value.replace("$", "").replace(",", ""))
                    if not amount.is_finite() or amount <= 0 or amount.as_tuple().exponent < -2:
                        raise ValueError("Enter a positive amount with no more than two decimal places.")
                except InvalidOperation as exc:
                    raise ValueError("Enter a positive amount of money.") from exc
                value = format(amount, ".2f")
            apply_interactive_branch(self.session, binding, "unknown" if value == "unknown" else "submit", submitted_text=value)
        # The preliminary script derives this value for original-creditor cases.
        if node in {"guided_plaintiff", "guided_creditor_type"} and script_fact(self.session, "field:PLAINTIFF") == "original":
            name = self.session.plaintiff_name
            apply_interactive_branch(self.session, "prelim_original_creditor", "submit" if name else "unknown", submitted_text=name)
        if not advance:
            return
        self.notices = []
        if self.pending_preliminary_route:
            if value == "unknown":
                self.current = node
                return
            route = self.pending_preliminary_route
            self.pending_preliminary_route = None
            self._drain(route)
            return
        order = list(PRELIMINARY_FIELDS)
        next_index = order.index(node) + 1
        next_node = order[next_index] if next_index < len(order) else PRELIMINARY_SUMMARY
        if next_node == "guided_original_creditor" and script_fact(self.session, "field:PLAINTIFF") == "original":
            next_node = order[next_index + 1]
        self.current = next_node

    def _drain(self, node_id: str) -> None:
        for _ in range(60):
            unresolved_fields = {"sol_creditor_type_resolve": ("guided_creditor_type", "sol_creditor_type"),
                                 "sol_oral_gate_resolve": ("guided_oral", "sol_oral_gate"),
                                 "fraud_creditor_type_resolve": ("guided_creditor_type", "fraud_creditor_type"),
                                 "mitigation_consolidation_resolve": ("guided_consolidation", "mitigation_consolidation"),
                                 "rescission_consolidation_resolve": ("guided_consolidation", "rescission_consolidation"),
                                 "accord_consolidation_resolve": ("guided_consolidation", "accord_consolidation"),
                                 "common_counts_suit_resolve": ("guided_suit_type", "common_counts_suit"),
                                 "excuse_suit_type_resolve": ("guided_suit_type", "excuse_suit_type")}
            if node_id in unresolved_fields:
                self.current, self.pending_preliminary_route = unresolved_fields[node_id]
                return
            if node_id in {key + "_confirm" for key in DEFENSES}:
                defense = node_id.removesuffix("_confirm")
                if defense in PARENT_FROM_NESTED:
                    choices = self.session.checkbox_selections.setdefault(defense, {})
                    choices["main"] = "include" if any(v == "include" for k, v in choices.items() if k != "main") else "exclude"
                    self.session.defense_selections[defense] = choices["main"]
                    target = self.answer_response if self.response_origin else self.notices
                    target.append(_script_text(CONTENT["parent_outcomes"][defense][
                        "selected" if choices["main"] == "include" else "empty"], self.session))
                if self.response_origin and defense not in PRESENTATION["confirmation_on_review_defenses"]:
                    choices = self.session.checkbox_selections.get(defense, {})
                    selected = "include" in choices.values()
                    self.answer_response.append(CONTENT["confirmation"]["selected" if selected else "empty"])
                    # Replay visits earlier summaries on every request. Feedback
                    # needs only the choices, not a full review with edit links.
                    self.answer_response.append("\n".join(
                        label + (": Check this box" if choices[box] == "include" else ": Leave unchecked")
                        for box, label in FEEDBACK_BOX_LABELS[defense].items() if box in choices))
                self.current = DEFENSES[defense]["summary"]
                return
            # Resolve uncertainty only when no Yes establishes Laches.
            if node_id in {"laches_pending", "laches_statements_pending", "laches_lost_info_pending"}:
                node_id = "laches_outcome"
            if node_id == "laches_unresolved":
                node_id = next(issue for fact, issue in [("laches", "laches_unresolved"),
                    ("laches_statements", "laches_statements_unresolved"),
                    ("laches_lost_info", "laches_lost_info_unresolved")]
                    if script_fact(self.session, "answer:" + fact) not in {"yes", "no"})
            definition = TREE.node(node_id)
            if definition.discussion_topic not in {spec["label"] for spec in DEFENSES.values()}:
                raise ValueError("This defense is not included in the guided prototype.")
            if definition.kind == "condition":
                branch = _condition(self.session, definition.condition_key)
                self.calculations[node_id] = branch
                apply_interactive_branch(self.session, node_id, branch)
                node_id = TREE.route(node_id, branch)
            elif definition.kind == "action":
                run_script_action(self.session, definition.action)
                text = render_node(node_id, None, self.session).question.split("\n\n", 1)[-1]
                if text.strip() and node_id not in {key + "_intro" for key, spec in DEFENSES.items() if "intro" in spec}:
                    if node_id not in PRESENTATION["response_only_nodes"]:
                        target = (self.answer_response if self.response_origin and node_id not in
                                  PRESENTATION["context_actions"] else self.notices)
                        target.append(text)
                operation, defense, *_ = definition.action.split(":")
                if operation == "script_finish":
                    self.finish_reasons[defense] = text
                    self.current = DEFENSES[defense]["summary"]
                    return
                if operation == "script_resolve":
                    self.finish_reasons[defense] = "Clinic staff have addressed this issue. Follow their guidance when completing Attachment 4. This tool has not selected this defense’s checkbox."
                    if self.response_origin:
                        self.answer_response.append(self.finish_reasons[defense])
                    self.current = DEFENSES[defense]["summary"]
                    return
                node_id = definition.next
            else:
                self.current = node_id
                return
        raise ValueError("The script could not resolve this page.")

    def _intake_page(self) -> dict:
        spec = PRELIMINARY_FIELDS[self.current]
        kind = spec["input_type"]
        default = self.defaults.get(spec["field"])
        if type(default) is bool:
            default = "yes" if default else "no"
        elif default is None and spec["field"] in self.defaults and kind == "date" and spec["allow_missing"]:
            default = "missing"
        if default is not None and kind == "currency":
            default = str(default).replace("$", "").replace(",", "")
        creditor = script_fact(self.session, "field:PLAINTIFF")
        payment = self.session.preliminary_fields.get("LAST-PAYMENT-DATE")
        help_blocks = []
        for block in spec["help"]:
            if "creditor_type" in block and block["creditor_type"] != creditor:
                continue
            if "payment_status" in block and (payment is None or block["payment_status"] != payment.complaint_status):
                continue
            help_blocks.append(_script_text(block["text"], self.session))
        help_text = "\n\n".join(help_blocks)
        is_personal = spec["field"] in {"ORAL", "RECOGNIZE", "CONSOLIDATION"}
        body = "Answer about your experience with this account." if is_personal else "Record what the complaint and its attachments say. This does not mean you agree with the claim."
        if self.pending_preliminary_route:
            body = "This preliminary field is still unresolved. Use the explanation or ask clinic staff, then update the field to continue."
        return {"title": spec["title"], "body": [body], "input_type": kind,
                "field_label": spec["label"], "default_value": default, "options": spec.get("options", []), "help_text": help_text,
                "date_alternatives": ([{"value": "missing", "label": "Not listed in the complaint"}] if kind == "date" and spec["allow_missing"] else []) + ([{"value": "unknown", "label": "I’m not sure"}] if kind == "date" else []),
                "why": help_blocks[0] if help_blocks else "Confirm this preliminary field before reviewing defenses.", "stage": 0}

    def _rows(self, defense: str = DEFENSE) -> list[dict]:
        choices = self.session.checkbox_selections.get(defense, {})
        rows = []
        labels = BOX_LABELS if defense == DEFENSE else {"main": (DEFENSES[defense]["label"], "Main checkbox")}
        if defense != DEFENSE:
            for node in TREE.nodes:
                for box in node.selection_checkboxes:
                    if box.defense_id == defense:
                        labels.setdefault(box.checkbox_id, (box.label, box.checkbox_id.capitalize() + " indented checkbox"))
        for box, (label, detail) in labels.items():
            index = next((i for i, answer in enumerate(self.history)
                          if answer.node_id in TREE.node_map and any(
                              b.checkbox_id == box and b.defense_id == defense for b in TREE.node(answer.node_id).selection_checkboxes)), None)
            selection = choices.get(box)
            rows.append({"id": box, "defense_id": defense, "label": label, "detail": detail,
                         "checked": selection == "include", "status": "Selected" if selection == "include" else "Not selected" if selection == "exclude" else "Not offered on this path",
                         "edit_index": index, "derived": box == "main" and defense in PARENT_FROM_NESTED})
        return rows

    def case_details(self) -> list[dict]:
        labels = {"original": "Original creditor", "buyer": "Debt buyer", "yes": "Yes", "no": "No",
                  "breach": "Breach of contract", "common": "Common counts", "both": "Both"}
        details = []
        for page, spec in PRELIMINARY_FIELDS.items():
            field = self.session.preliminary_fields.get(spec["tag"])
            value = field.value if field else None
            if isinstance(value, date):
                display = value.strftime("%b %d, %Y")
            else:
                display = labels.get(str(value), str(value)) if value else "Not stated" if field and field.status == "missing" else "Not yet confirmed"
            indices = [i for i, answer in enumerate(self.history) if answer.node_id == page]
            derived = page == "guided_original_creditor" and script_fact(self.session, "field:PLAINTIFF") == "original"
            details.append({"node_id": page, "label": spec["label"], "value": display, "derived": derived,
                            "edit_index": None if derived else indices[-1] if indices else None})
        return details

    def review_answers(self, defense: str = DEFENSE) -> list[dict]:
        """Only the dependencies and evidence used for this defense's results.

        Explicit checkbox decisions already appear in the checklist. Ambiguity
        has no factual prerequisites; its result is the litigant's own choice.
        """
        if defense not in {DEFENSE, "ambiguity", "laches"}:
            result = []
            dependencies = {"fraud": ["guided_creditor_type"],
                "failure_to_mitigate": ["guided_consolidation"], "common_counts": ["guided_suit_type"],
                "rescission": ["guided_consolidation"], "lack_of_consideration": ["guided_recognize"],
                "accord_satisfaction": ["guided_consolidation"], "excuse_breach": ["guided_suit_type"],
                "capacity": ["guided_open_date"], "waiver": ["guided_creditor_type"]}
            details = {row["node_id"]: row for row in self.case_details()}
            result.extend(details[key] for key in dependencies.get(defense, []))
            for index, answer in enumerate(self.history):
                node = TREE.node_map.get(answer.node_id)
                if node and node.discussion_topic == DEFENSES[defense]["label"] and node.discussion_mode != "questions" and not node.selection_checkboxes:
                    result.append({"node_id": node.id, "label": _script_text(node.question, self.session),
                                   "value": {"yes": "Yes", "no": "No", "unknown": "Not sure"}.get(answer.value, answer.value), "edit_index": index})
            return result
        if defense == "ambiguity":
            return []
        if defense == "laches":
            records = {answer.node_id: (index, answer) for index, answer in enumerate(self.history)}
            facts = [("laches", "Locked out of online portal"), ("laches_statements", "Relying only on provided statements"),
                     ("laches_lost_info", "Information harder to find because of delay")]
            # One affirmative fact establishes the offer. Otherwise, all three
            # negative answers are needed to explain why it was not offered.
            witness = next((item for item in facts if script_fact(self.session, "answer:" + item[0]) == "yes"), None)
            result = []
            for node, label in [witness] if witness else facts:
                source = node + "_resolve" if node + "_resolve" in records else node
                if source in records:
                    index, answer = records[source]
                    result.append({"node_id": source, "label": label, "value": {"yes": "Yes", "no": "No", "unknown": "Not sure"}[answer.value], "edit_index": index})
            return result
        plan = _dependency_plan(self, {}, None)
        facts = load_dependency_map()["facts"]
        records = {answer.node_id: (index, answer) for index, answer in enumerate(self.history)}
        details = {row["node_id"]: row for row in self.case_details()}
        questions = {"sol_payment_estimate_agree": "Agree with complaint’s last-payment date",
                     "sol_payment_age": "Last payment a year or more before filing"}
        rows = {}
        for fact in plan.used_facts:
            spec = facts[fact]
            if "review_evidence" in spec:
                evidence = next((item for item in spec["review_evidence"] if item["answer"] in records
                                 and records[item["answer"]][1].value in item["values"]), None)
                if evidence is None:
                    continue
                fields, answers = evidence["fields"], evidence["questions"]
            else:
                fields, answers = spec["fields"], []
            for node in fields:
                rows[node] = details[node]
            for node in answers:
                if node in records:
                    index, answer = records[node]
                    rows[node] = {"node_id": node, "label": questions[node],
                                  "value": {"yes": "Yes", "no": "No", "unknown": "Not sure"}[answer.value],
                                  "edit_index": index}
        return list(rows.values())

    def _current_defense(self) -> str:
        if self.current in SUMMARY_DEFENSES:
            return SUMMARY_DEFENSES[self.current]
        if self.current in INTRO_DEFENSES:
            return INTRO_DEFENSES[self.current]
        if self.current in TREE.node_map:
            return next(key for key, spec in DEFENSES.items() if spec["label"] == TREE.node(self.current).discussion_topic)
        return DEFENSE

    def _summary_help(self, defense: str) -> str:
        if defense in self.finish_reasons:
            intro = _script_text(CONTENT["nodes"][defense + "_intro"]["explanation"], self.session)
            return intro + "\n\n" + self.finish_reasons[defense]
        return render_node(defense + "_confirm", None, self.session).explanation.text

    def page(self) -> dict:
        preliminary = self.current in PRELIMINARY_FIELDS or self.current in {"guided_welcome", PRELIMINARY_SUMMARY}
        defense = self._current_defense()
        section = DEFENSES[defense]["label"]
        section_number = 1 if preliminary else len(DEFENSES) + 1 if self.current == COMPLETE else list(DEFENSES).index(defense) + 2
        if self.current in PRELIMINARY_FIELDS:
            page = self._intake_page()
        elif self.current == "guided_welcome":
            prototype_scope = "This prototype currently includes preliminary fields and 17 defenses. Standing and Privity (3), Failure to State a Cause of Action (4), Identity Theft (6), and Wrong Party (7) are omitted. Ask clinic staff about those defenses."
            page = {"title": "Overview", "body": CONTENT["overview"], "input_type": "continue", "stage": 0,
                    "why": prototype_scope, "help_text": "\n\n".join([*CONTENT["overview"], prototype_scope]),
                    "visual": {"type": "overview"}, "next_label": "Start review"}
        elif self.current == PRELIMINARY_SUMMARY:
            page = {"title": "Review your preliminary fields", "body": ["These fields will be reused in the defense sections. Use Change to update an answer."],
                    "input_type": "preliminary_summary", "stage": 2, "next_label": "Continue to Statute of Limitations",
                    "why": "You’ll review each defense using these recorded fields. You do not need to enter them again.",
                    "help_text": "Review the recorded preliminary fields before continuing. Recording a complaint field does not mean you agree with the plaintiff’s claim."}
        elif self.current in INTRO_DEFENSES:
            explanation = _script_text(CONTENT["nodes"][defense + "_intro"]["explanation"], self.session)
            restatements = [_script_text(v.text, self.session) for v in TREE.node(defense + "_intro").fact_restatements if _condition(self.session, v.fact_key) == v.equals]
            page = {"title": section, "body": [explanation, *restatements], "input_type": "continue", "stage": 1,
                    "next_label": "Review this defense", "why": "We’ll reuse your preliminary fields and ask only the additional questions needed for this defense.",
                    "help_text": explanation}
        elif self.current in {*SUMMARIES, COMPLETE}:
            unresolved = list(self.session.defense_open_questions.values())
            rows = self._rows(defense)
            finished = self.current in SUMMARIES and defense in self.finish_reasons
            next_index = list(DEFENSES).index(defense) + 1
            next_label = "Continue to " + DEFENSES[list(DEFENSES)[next_index]]["label"] if next_index < len(DEFENSES) else "Finish review"
            confirmation = CONTENT["confirmation"]["selected" if any(r["checked"] for r in rows) else "empty"]
            page = {"title": "Your review is complete" if self.current == COMPLETE else f"{section} review complete" if finished else f"Review your {section} selections", "stage": 2,
                    "body": ["You’ve reviewed the 17 defenses included in this prototype. Raise your hand and notify clinic staff if you have further questions."] if self.current == COMPLETE else (["No checkboxes were offered in this section. Review the answers below or continue."]
                          if self.finish_reasons[defense] in self.answer_response else [self.finish_reasons[defense]]) if finished else [*self.notices, ("Review the checkbox selections below. Use Change to update an answer before continuing." if confirmation in self.answer_response else confirmation)],
                    "input_type": "complete" if self.current == COMPLETE else "summary", "rows": rows,
                    "review_answers": self.review_answers(defense),
                    "why": "Use Change to revisit an answer or choice." + (" The first and third SOL boxes share one question." if defense == DEFENSE else " Each defense’s checkbox choice is recorded separately."),
                    "help_text": self._summary_help(defense),
                    "open_questions": [x["reason"] for x in unresolved],
                    "next_label": next_label}
            if self.current == COMPLETE:
                page["groups"] = [{"section": spec["label"], "rows": self._rows(key)} for key, spec in DEFENSES.items()]
                page["rows"] = [row for group in page["groups"] for row in group["rows"]]
                page["review_answers"] = list({row["node_id"]: row for key in DEFENSES for row in self.review_answers(key)}.values())
                page["help_text"] = "\n\n".join(self._summary_help(key) for key in DEFENSES)
        else:
            definition = TREE.node(self.current)
            rendered = render_node(self.current, None, self.session)
            paragraphs = rendered.question.split("\n\n")[1:]
            question = paragraphs[-1]
            if self.current == self.moved_preamble or self.current in PRESENTATION["response_only_preambles"]:
                paragraphs = [question]
            prefix, remaining_question = _response_prefix(self.current, self.session)
            if prefix:
                question = remaining_question
                paragraphs = [question]
            page = {"title": question, "body": [*self.notices, *paragraphs[:-1]], "input_type": "choice", "stage": 1,
                    "help_text": rendered.explanation.text, "why": "Your answer determines which part of this defense we review next. You choose which offered boxes to check.",
                    "options": [{"value": b.id, "label": b.label} for b in definition.branches]}
            if definition.kind == "input":
                page["input_type"] = "text"
                page["field_label"] = question
                page["allow_unknown"] = any(b.id == "unknown" for b in definition.branches)
            elif definition.discussion_mode == "questions":
                page["title"] = "Ready to return to the pending question?"
                page["body"] = [*self.notices, "Ask a clarifying question here or speak with clinic staff before choosing an answer."]
                page["options"] = [{"value": "retry", "label": "I’m ready to answer again"}, {"value": "unknown", "label": "I still need help"}]
            elif definition.discussion_mode == "referral":
                page["options"] = [{"value": "resolved", "label": "Clinic staff have addressed this issue"},
                                   {"value": "unknown", "label": "I still need clinic staff guidance"}]
            elif self.current == "sol_payment_estimate_agree":
                page["options"] = [{"value": "yes", "label": "Yes, that date is correct"}, {"value": "no", "label": "No, that date is incorrect"}, {"value": "unknown", "label": "I’m not sure"}]
                page["why"] = "Payment timing is one fact used in this section. Check whether the complaint’s date matches your records."
            elif definition.selection_checkboxes:
                page["options"] = [{"value": "yes", "label": "Yes, check both boxes" if definition.checkboxes else "Yes, check this box"}, {"value": "no", "label": "No, leave both unchecked" if definition.checkboxes else "No, leave this box unchecked"}, {"value": "unknown", "label": "I’m not sure yet"}]
            if self.current in {"sol_payment_estimate_agree", "sol_payment_age"}:
                payment = self.session.preliminary_fields.get("LAST-PAYMENT-DATE")
                payment_date = payment.complaint_value if payment else None
                filing = self.session.filing_date
                if isinstance(payment_date, date) and filing:
                    page["visual"] = {"type": "timeline", "payment": payment_date.isoformat(), "filing": filing.isoformat(),
                                      "months": round((filing - payment_date).days / 30.4375, 1)}
        if self.current in PRESENTATION["explanation_on_question"].get(defense, []):
            explanation = _script_text(CONTENT["nodes"][defense + "_intro"]["explanation"], self.session)
            question = page["title"]
            page["body"] = [explanation, *[text for text in page["body"] if text != explanation], question]
            page["question_text"] = question
            page["title"] = section
        page.update({"node_id": self.current, "can_back": bool(self.history), "case_details": self.case_details(),
                     "section": "Preliminary fields" if preliminary else section if self.current != COMPLETE else "Review complete",
                     "section_number": section_number, "section_count": len(DEFENSES) + 1,
                     "progress_stage": len(DEFENSES) + 1 if self.current == COMPLETE else section_number - 1,
                     "next_label": page.get("next_label", "Next"), "answer_count": len(self.history)})
        if self.revision:
            page["revision_notice"] = "Your other answers have been kept. Only questions that could affect the available checkboxes need review."
            if self.current in {*SUMMARIES, COMPLETE}:
                previous_review = GuidedSolReview(self.defaults, debug_section=self.debug_section).replay(self.revision.previous_history)
                before = {(row["defense_id"], row["id"]): row for key in DEFENSES for row in previous_review._rows(key)}
                page["changes"] = []
                for row in page["rows"]:
                    previous = before[row["defense_id"], row["id"]]
                    if (row["checked"], row["status"]) != (previous["checked"], previous["status"]):
                        row["previous_status"] = previous["status"]
                        page["changes"].append({"label": row["label"], "before": previous["status"], "after": row["status"]})
                page["revision_notice"] = ("Your details were updated. Review the checkbox changes below." if page["changes"]
                                           else "Your details were updated. Your checkbox selections are unchanged.")
        if page["input_type"] == "choice":
            page["answer_responses"] = {option["value"]: self.preview_response(option["value"])
                                        for option in page["options"]}
        page["dynamic_response"] = (page["input_type"] in {"text", "date", "currency"} and
                                   (self.current in TREE.node_map or self.pending_preliminary_route is not None))
        formatter = ScriptFormatter(self.session)
        page["body_blocks"] = formatter.blocks(page["body"])
        page["help_blocks"] = formatter.blocks([page["help_text"]])
        if "answer_responses" in page:
            page["answer_response_blocks"] = {value: formatter.blocks(texts)
                                               for value,texts in page["answer_responses"].items()}
        question_blocks = formatter.blocks([page["title"]])
        if any(block["type"] == "list" for block in question_blocks):
            # Keep list items out of the heading while preserving their place
            # above the answer control on this same question page.
            original_title = page["title"]
            page["title"] = question_blocks[0]["text"]
            page["body_blocks"].extend(question_blocks[1:])
            if page.get("field_label") == original_title:
                page["field_label"] = page["title"]
        return page

    def chat_node(self) -> CurrentNode:
        page = self.page()
        return CurrentNode(node_id=self.current, question=page.get("question_text", page["title"]), discussion_topic=page["section"], discussion_mode="questions",
                           explanation=NodeExplanation(text=page["help_text"]))


def _payment_date(review: GuidedSolReview) -> date | None:
    entry = review.session.preliminary_fields.get("LAST-PAYMENT-DATE")
    return entry.complaint_value if entry and isinstance(entry.complaint_value, date) else None


def _timing_result(payment: date | None, filing: date | None) -> bool | None:
    if payment is None or filing is None or payment > filing:
        return None
    return payment <= calendar_cutoff(filing, 1)


def _saved_answers(defaults: dict, history: list[GuidedAnswer], *, debug_section: str | None = None) -> dict[str, SavedAnswer]:
    review = GuidedSolReview(defaults, debug_section=debug_section)
    saved = {}
    for answer in history:
        # Validate the source path before treating any of its answers as reusable.
        review._restore_separate_intro(answer)
        if answer.node_id != review.current and not review._legacy_intro(answer):
            raise ValueError("The saved review no longer matches the script.")
        saved[answer.node_id] = SavedAnswer(answer=answer, payment_date=_payment_date(review), filing_date=review.session.filing_date)
        review._apply_answer(answer)
        review.history.append(answer)
    return saved


def _reusable_answer(review: GuidedSolReview, saved: dict[str, SavedAnswer], plan: SolDependencyPlan | None = None) -> GuidedAnswer | None:
    node = review.current
    record = saved.get(node)
    if node in {"laches", "laches_statements", "laches_lost_info"}:
        resolution = saved.get(node + "_resolve")
        if resolution and resolution.answer.value in {"yes", "no"}:
            return resolution.answer.model_copy(update={"node_id": node, "automatic": True})
    if plan is not None and node in plan.required_questions:
        return None
    if node == "sol_payment_estimate_agree":
        payment, filing = _payment_date(review), review.session.filing_date
        if record and record.answer.value == "yes" and record.payment_date == payment:
            return record.answer.model_copy(update={"automatic": True})
        if record and record.answer.value in {"yes", "reuse_comparison"}:
            before = _timing_result(record.payment_date, record.filing_date)
            after = _timing_result(payment, filing)
            if before is not None and before == after:
                return GuidedAnswer(node_id=node, value="reuse_comparison", automatic=True,
                                    timing_basis=TimingBasis(kind="comparison", payment_date=record.payment_date, filing_date=record.filing_date))
        if record and record.answer.value in {"no", "unknown"} and record.payment_date == payment:
            return record.answer.model_copy(update={"automatic": True})
        estimate = saved.get("sol_payment_age")
        if estimate and estimate.filing_date == filing and estimate.answer.value in {"yes", "no", "unknown"}:
            return GuidedAnswer(node_id=node, value="reuse_estimate", automatic=True,
                                timing_basis=TimingBasis(kind="estimate", filing_date=filing))
        return None
    if record is None:
        if node == "guided_original_creditor":
            # A creditor-type edit may add this name page. SOL eligibility does
            # not depend on the name; leave it unknown instead of asking again.
            return GuidedAnswer(node_id=node, value="unknown", automatic=True)
        return None
    if review.pending_preliminary_route and node in PRELIMINARY_FIELDS and record.answer.value == "unknown":
        return None
    if node in {*SUMMARIES, COMPLETE, "guided_welcome"}:
        return None
    if node.startswith("guided_"):
        return record.answer.model_copy(update={"automatic": True})
    definition = TREE.node(node)
    if plan is not None and definition.selection_checkboxes and definition.selection_checkboxes[0].defense_id == DEFENSE:
        if any(plan.availability[box.checkbox_id] is not True for box in definition.selection_checkboxes):
            return None
    value = record.answer.value
    if node in {"laches", "laches_statements", "laches_lost_info"} and value == "unknown":
        # An explicit unknown may be irrelevant when another fact is Yes. The
        # outcome gate still requires clarification when no Yes is available.
        return record.answer.model_copy(update={"automatic": True})
    if node in {"mitigation_contact", "mitigation_contact_resolve"} and value == "unknown":
        # November 7 permits this uncertainty after the contact clarification.
        return record.answer.model_copy(update={"automatic": True})
    if node == "sol_payment_age":
        return record.answer.model_copy(update={"automatic": True}) if record.filing_date == review.session.filing_date else None
    if definition.kind == "input":
        return record.answer.model_copy(update={"automatic": True}) if value != "unknown" else None
    if definition.discussion_mode == "questions" or value not in {b.id for b in definition.branches}:
        return None
    # A reached decision already passed the current script's eligibility gates.
    # Reuse only a recorded explicit choice for those exact boxes.
    if value in {"yes", "no", "original", "buyer", "resolved"}:
        return record.answer.model_copy(update={"automatic": True})
    return None


def _dependency_plan(review: GuidedSolReview, saved: dict[str, SavedAnswer], changed_field: str | None) -> SolDependencyPlan:
    """Work backward from the checkbox goals using all still-valid known facts."""
    records = {**saved, **_saved_answers(review.defaults, review.history, debug_section=review.debug_section)}
    assessment = GuidedSolReview(review.defaults, debug_section=review.debug_section)
    for node in PRELIMINARY_FIELDS:
        if node in records:
            assessment._intake(node, records[node].answer.value, advance=False)
    for node in ("sol_creditor_type_resolve", "sol_oral_gate_resolve"):
        record = records.get(node)
        if record and record.answer.value in {"yes", "no", "original", "buyer"}:
            apply_interactive_branch(assessment.session, node, record.answer.value)

    assessment.current = "sol_payment_estimate_agree"
    retained = _reusable_answer(assessment, records)
    timing, timing_question = None, "sol_payment_age"
    if retained and retained.value in {"yes", "reuse_comparison"}:
        result = _timing_result(_payment_date(assessment), assessment.session.filing_date)
        if result is not None:
            timing = "qualifying" if result else "recent"
    elif retained is None and _payment_date(assessment) is not None and assessment.session.filing_date is not None:
        timing_question = "sol_payment_estimate_agree"
    if timing is None:
        estimate = records.get("sol_payment_age")
        if estimate and estimate.filing_date == assessment.session.filing_date:
            timing = {"yes": "qualifying", "no": "recent", "unknown": "uncertain"}.get(estimate.answer.value)

    choices = {}
    for node, record in records.items():
        if node in TREE.node_map:
            for box in TREE.node(node).selection_checkboxes:
                if box.defense_id == DEFENSE:
                    choices[box.checkbox_id] = record.answer.value
    creditor = script_fact(assessment.session, "field:PLAINTIFF")
    oral = script_fact(assessment.session, "field:ORAL")
    return plan_checkbox_review(
        {"plaintiff_type": creditor if creditor in {"original", "buyer"} else None,
         "payment_timing": timing, "oral_agreement": oral if oral in {"yes", "no"} else None},
        {"plaintiff_type": "guided_creditor_type", "payment_timing": timing_question,
         "oral_agreement": "guided_oral"}, choices, changed_field,
    )


def _resume_review(review: GuidedSolReview, revision: GuidedRevision) -> GuidedSolReview:
    saved = {record.answer.node_id: record for record in revision.saved_answers}
    plan = _dependency_plan(review, saved, revision.changed_field)
    revision = revision.model_copy(update={"plan": plan})
    for _ in range(400 - len(review.history)):
        if review.current in {*SUMMARIES, COMPLETE}:
            break
        answer = _reusable_answer(review, saved, plan)
        if answer is None:
            break
        review._apply_answer(answer)
        review.history.append(answer)
    else:
        raise ValueError("The updated review needs too many steps. Return to the previous page.")
    if review.current in SUMMARY_DEFENSES:
        defense = SUMMARY_DEFENSES[review.current]
        visited = {answer.node_id for answer in review.history}
        # Reaching a summary settles this defense's path. A removed option must
        # not reappear from the edit cache if a later edit makes it eligible.
        saved = {key: record for key, record in saved.items()
                 if key in visited or key not in TREE.node_map or not any(
                     box.defense_id == defense for box in TREE.node(key).selection_checkboxes)}
        revision = revision.model_copy(update={"saved_answers": list(saved.values())})
    review.revision = revision
    return review


def edit_review(defaults: dict, request: GuidedEditRequest) -> GuidedSolReview:
    current = GuidedSolReview(defaults, debug_section=request.debug_section).replay(request.history)
    if request.edit_index >= len(request.history):
        raise ValueError("Choose an answer that is already part of the review.")
    original = request.history[request.edit_index]
    if original.node_id in {*CONTINUE_PAGES, COMPLETE}:
        raise ValueError("This page does not contain an editable answer.")
    # A completed revision becomes the baseline for the next edit. Choices that
    # disappeared from that path cannot be resurrected by a later change.
    in_progress = request.revision is not None and current.current not in {*SUMMARIES, COMPLETE}
    saved = {}
    if request.revision:
        for record in request.revision.saved_answers:
            node = TREE.node_map.get(record.answer.node_id)
            # Keep factual answers even when a previous path did not need them.
            # Removed checkbox choices, however, need a fresh explicit choice
            # when a later edit makes those boxes available again.
            future_choice = (node is not None and node.selection_checkboxes and current.current in SUMMARY_DEFENSES
                             and node.discussion_topic in {spec["label"] for spec in DEFENSES.values()}
                             and list(DEFENSES).index(next(key for key, spec in DEFENSES.items() if spec["label"] == node.discussion_topic))
                             > list(DEFENSES).index(SUMMARY_DEFENSES[current.current]))
            if in_progress or node is None or not node.selection_checkboxes or node.discussion_topic == "Ambiguity" or future_choice:
                saved[record.answer.node_id] = record
    saved.update(_saved_answers(defaults, request.history, debug_section=request.debug_section))
    saved.pop(original.node_id, None)
    for field, resolution in {"guided_creditor_type": "sol_creditor_type_resolve", "guided_oral": "sol_oral_gate_resolve"}.items():
        if original.node_id == field and original.value != request.value:
            saved.pop(resolution, None)
    if original.value != request.value:
        if original.node_id == "guided_recognize":
            saved.pop("consideration_identity_resolve", None)
        if original.node_id in {"laches", "laches_statements", "laches_lost_info"}:
            saved.pop(original.node_id + "_resolve", None)
    revision = GuidedRevision(previous_history=request.revision.previous_history if in_progress else request.history,
                              saved_answers=list(saved.values()), changed_field=original.node_id)
    history = request.history[:request.edit_index] + [GuidedAnswer(node_id=original.node_id, value=request.value)]
    return _resume_review(GuidedSolReview(defaults, debug_section=request.debug_section).replay(history), revision)


def advance_review(defaults: dict, request: GuidedAdvanceRequest) -> GuidedSolReview:
    current = GuidedSolReview(defaults, debug_section=request.debug_section).replay(request.history)
    answer = GuidedAnswer(node_id=current.current, value=request.value)
    history = request.history + [answer]
    updated = GuidedSolReview(defaults, debug_section=request.debug_section).replay(history)
    if request.revision is None or updated.current == COMPLETE:
        updated.revision = request.revision
        return updated
    saved = {r.answer.node_id: r for r in request.revision.saved_answers}
    saved.pop(answer.node_id, None)
    revision = request.revision.model_copy(update={"saved_answers": list(saved.values())})
    return _resume_review(updated, revision)
