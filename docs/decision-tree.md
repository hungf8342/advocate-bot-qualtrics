# Decision-tree structure and field reuse

The current tree implements **Preliminary Questions (PRELIM-01)** followed by
**Affirmative Defenses (AFF-01)** from `Decision Tree Draft 9_24_2026.docx`.
The earlier `Tree-Structures.docx` describes an older workflow.

## YAML structure

Edit `src/advocate_bot_qualtrics/practice_areas/consumer_debt/interactive_tree.yaml`.
The existing schema is unchanged:

- `start_node_id` identifies the first question.
- A `choice` node has a `question` and `branches`; each branch has an `id`,
  `label`, and `target` node ID.
- An `input` node also declares an `input` field, type, valid branch, and unknown
  branch. Date inputs require a usable date before following `submit`.
- `idk_skip_branch_id` routes a bare “I don't know.” Missing information in the
  complaint has a separate `missing` branch where appropriate.
- An `action` node names host-side logic and a `next` node. Each `assess_*` action
  records a defense outcome and continues to the next subsection.
- The final `terminal` node enables open Q&A with `terminal_qa: true`.

The model's `next_node_id` is a **branch ID**, not a target node ID. The host resolves
the branch to its target. Non-answer intents must have a null `next_node_id`.

## Preliminary fields

Fields live in `session.preliminary_fields`, keyed by the document's bracketed tag.
The mappings are explicit in
`src/advocate_bot_qualtrics/practice_areas/consumer_debt/preliminary.py`;
bracketed text in a question is a label, not executable field-binding syntax.
Update those mappings when adding or renaming tagged nodes.

| Field | Stored answer / later use |
| --- | --- |
| `PLAINTIFF` | Original creditor or debt buyer; routes SOL, standing, and failure-to-state-a-cause questions |
| `PLAINTIFF-NAME` | Plaintiff's name, stored separately from creditor type |
| `RECOGNIZE` | Reused in identity theft and wrong party |
| `LAW-FIRM` | Plaintiff's law firm |
| `SUIT-TYPE` | Breach, common counts, both, missing, or unknown; controls both later claim-type gates |
| `ORAL` | Maps yes/no to oral/written in SOL |
| `AMOUNT` | Effective amount, updated if the user disagrees |
| `LAST-PAYMENT-DATE` | Effective payment date for the original-creditor SOL path; original complaint presence for failure to state a cause |
| `OPEN-DATE` | Effective opening date; original complaint presence for failure to state a cause |
| `STATEMENT` | Reused for the debt-buyer statement attachment question |
| `OWNERSHIP` | Reused for the tagged ownership/document questions |
| `VERIFIED` | Stored; PRELIM-01 specifies no additional routing consequence |
| `CONSOLIDATION` | Reused to word mitigation, rescission, and settlement-agreement questions |

The three agreement questions are also stored as `AMOUNT-AGREEMENT`,
`LAST-PAYMENT-DATE-AGREEMENT`, and `OPEN-DATE-AGREEMENT`.
`LANGUAGE` is in the draft's separate triage section, not PRELIM-01;
its affirmative-defense question still collects the answer later.

Each field contains its effective `value`, `status`, and `source_node`. Amount and
date entries also retain `complaint_value`, `complaint_status`, `complaint_source`,
and a `disputed` flag. On disagreement the old effective value is cleared and a
correction question is asked. If the correction is unknown, the field remains
unknown; the disputed complaint value is not restored. An unknown agreement answer
also leaves the effective value unknown.

For example, if the complaint reports a 2020 payment and the user corrects it to
2025, SOL uses 2025. The question “Does the complaint include a breach date?” still
uses the fact that a date was present. A missing date and an unknown date are kept
distinct. Payments specifically to a debt buyer are collected separately and do
not overwrite the tagged complaint payment date.

## Reuse and results

Before displaying a tagged defense question, the host replays the corresponding
stored answer through that node's existing YAML branch, including stored unknowns.
This happens after user answers and after action nodes. `session.reused_answers`
records the source node, and the reused answer retains the source confidence.
An unanswered field is not treated as a stored unknown: its question is still asked.

The full field values and provenance are available in the prototype's session debug
panel. They are session-local and reset with the conversation. The existing Excel
export remains a date/confidence export; it is not a full export of these fields.

Defense logic lives in `affirmative_defenses.py`. Results use `checked`, `unchecked`,
or `unresolved`. SOL compares the payment date strictly against a cutoff measured
backward from filing, and written-contract state law requires clinic confirmation.
Identity-theft and wrong-party referral paths remain unresolved and continue.

Run `.venv/bin/python -m pytest` after editing routing, field bindings, or prompts.
Tests cover field corrections, stored unknowns, valid branches, date cutoffs,
complete traversal, and the final summary/open-questions output.
