# Decision-tree structure and field reuse

The current tree implements **Preliminary Questions (PRELIM-01)** using the
October 11 preliminary document in `docs/source-material/2026-10-11/`, followed by
the 21 defenses in `docs/source-material/2026-10-25/2026.10.25 Affirmative-Defense-Scripts.docx`. These
documents define the YAML content and routing, together with explicit user
decisions about verification, selection, and clarification. The basic decision
tree is retained as reference material. The active flow ends after the 21st defense.

Parsed preliminary fields are supplied as a fact-only JSON object. See
[`examples/complaints/README.md`](../examples/complaints/README.md) for the temporary
contract and two imaginary inputs. Each parsed field has one agreement question;
"No" asks for the litigant's preferred value. `RECOGNIZE`, `CONSOLIDATION`, and
`ORAL` remain direct questions. All preliminary explanations appear with their
questions; help does not advance the tree.

## Code organization

- `core/engine.py` runs the conversation, records answers, follows branches,
  executes actions, and handles final Q&A.
- `core/process_chat.py` asks the model to interpret a message and validates the
  structured response against the current node's allowed branches.
- `core/tree_definition.py` defines and validates the YAML node schema.
- `practice_areas/consumer_debt/` owns the tree, captured fields, field reuse,
  rendering, defense rules, and export mapping.
- `llm/` contains model client calls; `scripts/interactive_chat_demo.py` provides
  the demo UI.

The former `advocate_bot_qualtrics.decision_tree` import paths have been removed.
Use `advocate_bot_qualtrics.core.engine` for the engine, `core.process_chat` for
chat processing, and `core.schemas` for chat/node models. Consumer-debt helpers
live in the corresponding practice-area modules. The package-level
`from advocate_bot_qualtrics import process_chat` entry point remains available.

## YAML structure

Edit `src/advocate_bot_qualtrics/practice_areas/consumer_debt/interactive_tree.yaml`.
The node schema includes:

- `start_node_id` identifies the first question.
- A `choice` node has a `question` and `branches`; each branch has an `id`,
  `label`, and `target` node ID.
- A `condition` node represents a document IF branch. It has branches and an
  empty question. Practice-area bindings evaluate already collected facts
  automatically, including unknown facts; the node is never shown to the litigant
  or sent to the model as a question. Missing facts lead to the document's uncertainty
  path. When a fact remains unresolved, a clarification question collects it before progression.
- A choice node may declare `validation: {type: enum, categories: ...}`. Each
  category key must match exactly one branch ID. The descriptions tell the
  model how to classify a free-text answer; the host still rejects any branch
  ID that is not declared on the node.
- An `input` node also declares an `input` field, type, valid branch, and unknown
  branch. Date inputs require a usable date before following `submit`.
- A node may declare an `explanation` with approved `text` and optional `images`.
  An image uses a project-relative path and alt text. When a user asks about
  that node, the host displays the approved text and images, then repeats the
  question without advancing. The initial plaintiff explanation references
  `complaint-examples/plaintiff.png`.
- Each preliminary node has a `title`, displayed before its explanation. An
  explanation can set `show_with_question: true` to appear automatically.
  Conditional explanations use ordered `blocks`, each with `text` and an optional
  `creditor_type` (`original` or `buyer`). Rendering filters blocks in place using
  the confirmed creditor type and replaces approved party-name placeholders.
  Unconditional paragraphs retain their original positions before, between, or
  after conditions. When type is unknown, both branches are labeled in document
  order. An explanation supplies either plain `text` or `blocks`, never both.
- `idk_skip_branch_id` routes a bare “I don't know.” Missing information in the
  complaint has a separate `missing` branch where appropriate.
- Defense conditions declare `condition_key`, evaluated in `affirmative_defenses.py`.
  Keys read verified intake fields (`field:`), complaint contents (`complaint:`),
  previously answered questions (`answer:`), or a named script condition (`rule:`).
  Every condition declares an `unknown` branch.
- A categorical clarification can declare `fact_key`; its answer resolves that
  fact for subsequent conditions, with its source retained in the session.
- A decision declares `checkbox: {defense_id, checkbox_id, label}` for a single
  box, or `checkboxes: [...]` for indented boxes offered together. One explicit
  Yes/No answer selects or declines all boxes in that group. Groups must contain
  unique boxes from one defense.
- `question_variants` stores approved alternate wording, and `fact_restatements`
  stores ordered conditional fact statements. Each entry has `fact_key`, `equals`,
  and `text`. The renderer picks the first matching wording variant and includes
  every matching fact statement. Consolidation wording stays in YAML.
- An `action` node has an `action` and `next`. `script_say` displays approved text;
  `script_finish` completes a section without offering a checkbox; `script_issue`
  records a pending question; `script_resolve` acknowledges staff resolution;
  `script_confirm` records completion after the user's readiness confirmation.
- The final `terminal` node enables open Q&A with `terminal_qa: true`.

The model's `next_node_id` is a **branch ID**, not a target node ID. The host resolves
the branch to its target. Non-answer intents must have a null `next_node_id`.
The tree starts with `verify_case_number`. Verification nodes have `yes`, `no`,
and `unknown` branches; their `no` branches lead to correction inputs or choices.
The creditor-type correction classifies answers as original creditor, debt buyer,
or not sure; a company name by itself does not establish the category.

## Preliminary fields

Fields live in `session.preliminary_fields`, keyed by the document's bracketed tag.
The mappings are explicit in
`src/advocate_bot_qualtrics/practice_areas/consumer_debt/preliminary.py`;
bracketed text in a question is a label, not executable field-binding syntax.
Update those mappings when adding or renaming tagged nodes.

The complaint filing date is verified after the opening-date question. External
`COMPLAINT.DATE` is stored as `FILING-DATE` and `session.filing_date`;
SOL uses this value without asking again. If the dates cannot be compared, the
original-creditor path asks directly whether the last payment was a year or more
before filing; an uncertain answer preserves the defense.

| Field | Stored answer / later use |
| --- | --- |
| `CASE.NUMBER` | Case number, verified first |
| `ORIGINAL.CREDITOR` | Original-creditor name, verified for debt-buyer or unknown creditor type |
| `PLAINTIFF` | Original creditor or debt buyer; routes SOL, standing, and failure-to-state-a-cause questions |
| `PLAINTIFF-NAME` | Plaintiff's name, stored separately from creditor type |
| `RECOGNIZE` | Reused in identity theft and wrong party |
| `LAW-FIRM` | Plaintiff's law firm |
| `FILING-DATE` | Complaint filing date, collected during preliminary intake and used in SOL screening |
| `SUIT-TYPE` | Breach, common counts, both, missing, or unknown; controls the additional date checks in failure to state a cause of action |
| `ORAL` | Stored oral/written answer; the one-year SOL preservation screen does not ask about state law |
| `AMOUNT` | Effective amount, updated if the user disagrees |
| `LAST-PAYMENT-DATE` | Complaint payment allegation for the SOL estimate; complaint presence for failure to state a cause. Litigant one-year estimates remain separate defense answers |
| `BREACH-DATE` | External `BREACH.DATE`; separately verified complaint breach date, used with last-payment presence in failure to state a cause |
| `OPEN-DATE` | Effective opening date; original complaint presence for failure to state a cause |
| `STATEMENT` | Attached final statement; for debt buyers it must include a charge-off date |
| `OWNERSHIP` | Plaintiff's asserted ownership / right to collect; reused for ownership assertions |
| `OWNERSHIP.PROOF` | Attached ownership evidence; reused for agreement/purchase-document questions |
| `VERIFIED` | Stored; PRELIM-01 specifies no additional routing consequence |
| `CONSOLIDATION` | Reused to word mitigation, rescission, and settlement-agreement questions |

The three agreement questions are also stored as `AMOUNT-AGREEMENT`,
`LAST-PAYMENT-DATE-AGREEMENT`, and `OPEN-DATE-AGREEMENT`.
`LANGUAGE` is outside PRELIM-01. The final Civil Code section 1632 defense asks for
the litigant's primary language when needed.

Each field contains its effective `value`, `status`, and `source_node`, plus
`verification` (`pending`, `confirmed`, `corrected`, or `unknown`) and the original
`parsed_value`. Parsed values are displayed immediately but do not become
effective answers until agreement or correction. Amount,
last-payment date, and account-opening date entries also retain `complaint_value`, `complaint_status`, `complaint_source`,
and a `disputed` flag. On disagreement the old effective value is cleared and a
correction question is asked. If the correction is unknown, the field remains
unknown; the disputed complaint value is not restored. An unknown agreement answer
also leaves the effective value unknown.

For example, if the complaint reports a 2020 payment, the SOL restatement uses
that complaint date. The litigant can disagree with the elapsed-time estimate and
answer the separate one-year question. That answer changes the preservation
result without replacing the scraped date or changing whether a date was present
in the complaint. Preliminary preferred values and original parsed values retain
their existing provenance.

## Reuse and results

The October 25 scripts govern all 21 defenses. General explanations and applicable
responses stay in YAML. `affirmative_defenses.py` evaluates factual conditions and
records workflow progress, without choosing boxes. A “Finish this defense” path
advances directly. General-only defenses lead directly to a choice.

Indented boxes mentioned together share one question: SOL’s first and third boxes
receive one answer that is recorded for each box. Other main, parent, and nested
choices follow their script questions. Choices live in
`session.checkbox_selections[defense_id][checkbox_id]` as `include` or `exclude`.
`session.defense_selections` retains main-box choices for callers that need them.
The same main checkbox is reused when both Failure to State a Cause of Action
claim groups apply, preserving the original choice and confidence. A combined choice applies only to the boxes explicitly named in its question.
Other child, parent, and main choices remain independent.

Each selection section ends with a checklist and a readiness question. Questions
about that section do not advance it. Unknown choices return to the same choice;
“No further questions” only returns to the pending question. Factual issues stay
in `session.defense_open_questions` until answered. Referral nodes accept
`resolved` only when the user confirms clinic staff addressed the issue. There is
no continue/skip branch on a referral, and staff resolution does not select boxes.

`session.script_facts` holds explicit clarification answers, with source nodes in
`script_fact_sources`. Clarifying an earlier account-problem answer updates its
reusable value. Uncredited-payment and insurance answers are reused in Excuse or
Breach of Contract with their source confidence. Reported fraud and suspected
identity theft are reused as facts independently of any checkbox selection.

Complaint-presence checks use confirmed complaint contents. A correction to the
litigant's preferred payment or opening date does not erase a date present in the
complaint. `BREACH.DATE` is collected separately: its correction question asks
what the complaint states, updates `complaint_value`, and preserves `parsed_value`.
The fourth Breach of Contract checkbox requires both payment and breach dates to
be absent. Unknown is distinct from absence and follows a clarification path.

Capacity skips both mental-condition questions when the user was under 18.
Identity theft and wrong party finish or refer according to the scripts, without
adding selection questions. Fraud asks the same plaintiff-focused question for
both creditor types. SOL retains the inclusive one-calendar-year comparison and
the script's explicit preservation path for an uncertain timing estimate; this
is separate from determining a legal deadline.

`discussion_topic` scopes Q&A to the active defense. `discussion_mode` distinguishes
screening, decision, questions, confirmation, and referral. The model receives
approved wording, statements actually visited, and recorded facts for that
section. Non-answer intents always have a null branch. The final terminal node
recaps explicit box choices, completed sections without offers, staff resolutions,
and open clinic questions. It remains available for Q&A.

The debug snapshot includes all checkbox choices, workflow progress, clarification
sources, and pending clinic issues. The existing Excel export remains a
date/confidence export. Reset restores the original unverified parsed input and
clears all choices and clarification state.

Run `.venv/bin/python -m pytest` after editing routing, field bindings, or prompts.
Tests compare wording with the source DOCX, exercise each offered checkbox,
validate branch constraints, cover date/attachment conditions, and traverse all
21 defenses to terminal Q&A across creditor, claim, recognition, oral-agreement,
and consolidation combinations.

The optional `--debug-shortcuts` flag enables **I agree with all** only during
preliminary intake. It retains prior answers and records unasked personal
questions as unknown. It does not bypass defense clarification or staff referral.
The [earlier integration review](affirmative-defense-integration-review.md) is
historical; the October 25 scripts and the user decisions in the
[source guide](source-material/2026-10-25/README.md) govern the active defenses.
