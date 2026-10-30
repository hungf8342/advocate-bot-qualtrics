# Guided Statute of Limitations and Ambiguity prototype

Run with the same development/demo environment as the chatbot:

```bash
.venv/bin/python scripts/guided_clickthrough_demo.py
```

Open <http://localhost:7861/>. The server binds to localhost and uses the imaginary
original-creditor complaint by default. To use another example:

```bash
.venv/bin/python scripts/guided_clickthrough_demo.py --complaint-fields examples/complaints/debt-buyer.json
.venv/bin/python scripts/guided_clickthrough_demo.py --blank
```

## Experience

The visual direction follows the provided “review payment timing” and “review
selections” screengrabs: a question panel, help sidebar, payment timeline, and a
separate checklist summary. Layouts adapt to narrow screens and keyboard use.

The guide has three separate sections: Preliminary fields, Statute of Limitations,
and Ambiguity. Each page asks at most one question. Text fields use short answers;
amount uses a positive currency input; dates use a date field with explicit
missing/unknown alternatives; other answers use radio choices.
Next requires an answer. Example values become effective facts only after the
user confirms them. The preliminary section covers all 18 fields in the October 30
preliminary-fields script, with its approved explanations and a separate review
page. For original creditors, original-creditor name is derived from plaintiff
name. SOL then starts with a dedicated page showing its full general explanation.

Defense sections reuse the recorded preliminary fields. SOL does not collect the
names, creditor type, dates, or oral-agreement status again when they are known.
Agreement with the complaint's payment date and a personal timing estimate are
distinct defense questions and remain on the relevant SOL paths. An unresolved
creditor type or oral status returns to that preliminary field, labeled as part
of the preliminary section, then resumes the pending defense route. Unknown oral
status does not block an ineligible SOL path. Ambiguity asks only its checkbox
question. Fields collected for future defenses are retained without adding those
defenses to this prototype.

“Review the answers used in this section” shows only active dependencies and the
evidence actually used to establish them. It excludes names and unrelated fields.
Debt buyers see plaintiff type and oral status, without payment dates. An original
creditor's agreed-date comparison includes the payment and filing dates and the
agreement answer. A personal timing estimate includes the filing date and estimate,
without the discarded or missing complaint payment date. Oral status is omitted
when timing makes every SOL box unavailable. Retained comparisons do not invent
agreement with an edited exact date. Ambiguity has no preliminary dependencies;
its explicit checkbox choice is already shown in its checklist. The final review
uses the relevant fields for the completed defenses. All 18 preliminary fields
remain available through “View case details” and in the preliminary summary.

The main SOL question is always offered to debt buyers, followed by the combined
first/third question and the second-box question when the agreement was oral.
Declining the main box does not decline any indented boxes. Original creditors
receive these offers only on the qualifying or uncertain timing path. Both selected and unchecked
boxes appear in the summary; boxes not offered on the chosen path are labeled.
“Change” returns to the original question, including the shared question for the
first and third boxes. Users can inspect and edit case details from any page.

After SOL, Ambiguity displays the October 30 explanation, including the example
about missing account history or a contract, and offers its main checkbox to
everyone. Its answer is independent of creditor type, timing, and SOL selections.
An undecided answer stays unresolved until the user returns and chooses Yes or No.
Each defense has its own selection summary, using the script's separate wording
for selected boxes and for no selected boxes. The final page shows both defenses.
A recent original-creditor payment displays a SOL result page without offering
boxes or recording selection confirmation, then continues to Ambiguity.

Back preserves previous answers. Editing a recorded answer reconciles the rest of
the saved review against the new script path. Independent preliminary fields are
retained, as are explicit choices for boxes still offered. Only newly relevant
questions and answers whose meaning depends on a changed fact need review. The planner starts
from the checkbox goals in `sol_checkbox_dependencies.yaml` and traces backward
to the facts needed for each offer. The forward script then presents required
questions in order and replays valid saved answers.

Examples:

- Plaintiff and original-creditor names are personalization only, including a
  replacement name. Changing either returns to the summary with existing choices.
- Moving an agreed payment date within the same one-year screening category
  retains the choices and returns to the summary. This reuses the screening
  result; it does not record agreement that the new exact date is correct.
- Changing a payment date across the threshold asks for the relevant date/timing
  confirmation. Changing the filing date recalculates the screen using an
  unchanged, previously agreed payment date, or asks again if the previous answer
  was only a personal timing estimate tied to the old filing date.
- Changing written to oral retains the other choices and asks about the newly
  offered second checkbox. Changing oral to written removes that option.
- Changing creditor type reuses eligible choices and asks only for newly needed
  timing or checkbox decisions. An uncollected original-creditor name stays
  unknown because that name does not control SOL checkbox eligibility. Still-valid factual answers
  remain reusable if the review later returns to a path that needs them.

The summary marks changed statuses and displays a confirmation when selections
are unchanged. Choices removed from a completed path are not automatically
restored if a later edit offers those boxes again. Back skips answers restored
automatically during an edit; Change links still let users inspect each retained
answer directly. Finishing requires a fresh summary confirmation after an edit.
Editing SOL retains a previously recorded Ambiguity choice. After reviewing the
updated SOL result/summary, the retained Ambiguity answer leads directly to its
summary without asking the checkbox question again. Editing Ambiguity preserves
all SOL answers. The two main boxes have separate Change links and identities.

## Clarification chat

“Ask a question” opens a small chat window about the current page, without losing
its pending answer. It uses the same configured model provider as the chatbot and
the dedicated `prompts/guided_sol_clarification_system.md` instructions. Approved
page explanations remain readable in the window if the provider is unavailable.

The backend always returns `next_node_id: null` and a non-answer intent. It cannot
record a fact or checkbox choice from the chat, even if a model returns a branch.
Page changes cancel pending chat requests and scope subsequent questions to the
new page. Related questions use approved script wording and confirmed facts only.

## Implementation

- `practice_areas/consumer_debt/sol_checkbox_dependencies.yaml`: the approved
  checkbox-to-rule-to-fact map, including personalization-only fields.
- `practice_areas/consumer_debt/sol_dependency_map.py`: backward dependency
  traversal, conditional fact requirements, and affected-checkbox discovery.
- `practice_areas/consumer_debt/guided_sol.py`: formatted answers, validated replay,
  and a two-defense page adapter over the existing YAML and deterministic rules.
- `practice_areas/consumer_debt/guided_defense_content.yaml`: October 30 SOL and
  Ambiguity wording and shared selected/empty confirmation copy. These copy
  overrides apply only to the click-through, including its clarification context.
- `practice_areas/consumer_debt/guided_preliminary_fields.yaml`: all 18 preliminary
  fields in source order, their formats, shared session bindings, and the approved
  field explanations, including conditional creditor-specific help.
- `scripts/guided_clickthrough_demo.py`: separate FastAPI server with static
  assets, stateless page/edit/advance endpoints, and a clarification endpoint.
- `scripts/assets/guided_sol/`: buildless HTML, CSS, and JavaScript.
- `tests/test_guided_sol.py`: branch correctness, date validation, changed paths,
  grouped choices, dependency-aware edits, summary comparisons, session isolation,
  and non-advancing chat.

The guided prototype remains separate from the chatbot UI. Both use the corrected
shared SOL route that offers debt buyers the main-defense question. The page adapter stops before Standing and Privity, the next
defense and performs no filing, document generation, Excel export, or account
storage. Progress lives in this browser tab's session storage and is cleared by
Start over or closing the tab. The mini chat requires the configured model service;
the form itself uses deterministic routing and works without model calls.
The October 30 prototype uses a new session-storage key; earlier SOL-only progress
is not loaded into this version.

The governing sources are the October 30 preliminary-fields and defense scripts
in `docs/source-material/2026-10-30/`. Other chatbot defenses retain their existing
source. Previously approved editing behavior remains in effect. This interface always shows a final
review page, including a path that finishes without offering any checkbox.

## SOL dependency map

| Offer | Rule | Facts needed |
| --- | --- | --- |
| Main defense | Debt buyer, or original creditor on qualifying/uncertain timing path | Plaintiff type; timing only for original creditors |
| First and third together | Same eligible path | Same facts as main; independent choice |
| Second | Eligible path plus an oral agreement | Eligible-path facts; oral-agreement answer |

A recent original-creditor payment ends without offering any boxes. An explicit
uncertain timing estimate follows the preservation path. Unknown plaintiff type
or oral-agreement status requires the relevant clarification. The evaluator does
not request payment timing for debt buyers, or oral details on an ineligible path.

Each revision includes its computed `plan` in the API response: potentially
`affected_boxes`, current `availability`, and `required_questions`. The plan is
recomputed from current facts and saved explicit choices, rather than trusting
an earlier browser-provided plan. The plan does not select any checkbox.

The plan also reports `used_facts`, tracing only the conditional dependencies
evaluated on the active path. The map's `review_evidence` entries distinguish
agreed-date comparisons, personal estimates, and retained comparisons. These
govern which answers appear in the section review, independently of the full case
details. A useful companion instruction for the source dependency tables is:
“Show only dependencies and supporting answers used on the current path. Omit
inactive alternatives and fields used only for display.” The tables govern offers;
the litigant's explicit decisions still determine which boxes are checked.
