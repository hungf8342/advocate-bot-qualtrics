# Decision-tree structure and field reuse

The current tree implements **Preliminary Questions (PRELIM-01)** using the
October 11 source documents in `docs/source-material/2026-10-11/`, followed by
the **Affirmative Defenses (AFF-01)** screening flow. The first nine defenses
use the updated explanations and the basic tree, with newer explanations and
explicit user decisions taking precedence where the sources differ.

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
The existing schema is unchanged:

- `start_node_id` identifies the first question.
- A `choice` node has a `question` and `branches`; each branch has an `id`,
  `label`, and `target` node ID.
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
- An `action` node names host-side logic and a `next` node. Each `assess_*` action
  records a defense outcome and continues to the next subsection. An `explain_*`
  action displays the general explanation and known facts without recording an
  assessment or requiring an extra confirmation.
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
original-creditor path asks directly whether the last payment was less than a year
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
| `SUIT-TYPE` | Breach, common counts, both, missing, or unknown; controls both later claim-type gates |
| `ORAL` | Stored oral/written answer; the one-year SOL preservation screen does not ask about state law |
| `AMOUNT` | Effective amount, updated if the user disagrees |
| `LAST-PAYMENT-DATE` | Complaint payment allegation for the SOL estimate; complaint presence for failure to state a cause. Litigant one-year estimates remain separate defense answers |
| `OPEN-DATE` | Effective opening date; original complaint presence for failure to state a cause |
| `STATEMENT` | Attached final statement; for debt buyers it must include a charge-off date |
| `OWNERSHIP` | Plaintiff's asserted ownership / right to collect; reused for ownership assertions |
| `OWNERSHIP.PROOF` | Attached ownership evidence; reused for agreement/purchase-document questions |
| `VERIFIED` | Stored; PRELIM-01 specifies no additional routing consequence |
| `CONSOLIDATION` | Reused to word mitigation, rescission, and settlement-agreement questions |

The three agreement questions are also stored as `AMOUNT-AGREEMENT`,
`LAST-PAYMENT-DATE-AGREEMENT`, and `OPEN-DATE-AGREEMENT`.
`LANGUAGE` is in the draft's separate triage section, not PRELIM-01;
its affirmative-defense question still collects the answer later.

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

Before displaying a tagged defense question, the host replays the corresponding
stored answer through that node's existing YAML branch, including stored unknowns.
This happens after user answers and after action nodes. `session.reused_answers`
records the source node, and the reused answer retains the source confidence.
An unanswered field is not treated as a stored unknown: its question is still asked.

The full field values and provenance are available in the prototype's session debug
panel. The sidebar shows parsed fields with their verification status. They are
session-local; reset restores the original parsed input as awaiting verification. The existing Excel
export remains a date/confidence export; it is not a full export of these fields.

Defense logic lives in `affirmative_defenses.py`. Results use `checked`, `unchecked`,
or `unresolved`. The first nine defenses show their document explanation before
personalized facts, questions, and application. General explanations are also
available as approved help on their question nodes.

- SOL is a clinic preservation screen, separate from the legal deadline. Debt
  buyers always preserve it. For original creditors, agreement with the complaint
  estimate uses an inclusive calendar-year comparison against filing. Otherwise,
  “Was your last payment less than a year before filing?” maps Yes to unchecked,
  No to checked, and uncertainty to checked. State-law and contract-type questions
  are no longer part of this screen.
- Ambiguity and mistake retain their basic-tree questions and broad-defense explanations.
- Standing for original creditors checks the ownership assertion, without adding
  an agreement-attachment requirement. Debt buyers preserve it.
- Failure to state a cause uses attached ownership proof and the complaint's
  opening/payment-date presence for original creditors. Debt buyers need either
  qualifying transfer documents or a final statement with a charge-off date;
  breach-of-contract claims (including Both) additionally check both dates.
  Neither attachment means preservation without further claim/date questions.
- Identity theft and wrong party reuse account recognition. Suspected cases stay
  unresolved and refer to clinic staff. Uncertain cases offer help, then continue
  with an unresolved result included in the final open questions.
- Laches asks three separate questions, in document order, and preserves if any
  answer is Yes. All No means unchecked; remaining uncertainty means unresolved.
- Fraud reuses identity-theft suspicion. A Yes preserves it immediately. No,
  uncertainty, or a skipped identity-theft question leads to the hidden-facts
  question, worded with both parties for debt buyers and the plaintiff for original creditors.

Run `.venv/bin/python -m pytest` after editing routing, field bindings, or prompts.
Tests cover field corrections, stored unknowns, valid branches, date cutoffs,
complete traversal, and the final summary/open-questions output.

The optional demo flag `--debug-shortcuts` enables **I agree with all** only during
preliminary intake. It confirms remaining parsed values, retains prior answers,
records unasked personal questions as unknown, and follows existing defense reuse
and action paths. Synthetic records have zero confidence and `skipped: true`;
`debug_bulk_accepted` lists the bulk-confirmed nodes. The shortcut is disabled in
normal engine construction and does not apply to defense questions or final Q&A.

The [October defense integration review](affirmative-defense-integration-review.md)
is historical; subsequent source revisions and the decisions above govern the
implemented first nine defenses.
