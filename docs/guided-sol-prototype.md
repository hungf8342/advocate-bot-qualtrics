# Guided affirmative-defense prototype

Run with the development/demo environment:

```bash
.venv/bin/python scripts/guided_clickthrough_demo.py
```

Open <http://localhost:7861/>. The server binds to localhost and defaults to the
imaginary original-creditor complaint. Use `--complaint-fields PATH` for another
fact-only example or `--blank` to start without prefilled examples.

## Source and scope

The governing defense source is [the November 7 script](source-material/2026-11-07/2026.11.07%20Affirmative-Defense-Scripts.docx).
The prototype covers 17 defenses in Attachment 4 order: 1, 2, 5, 8, and 9–21.
Standing and Privity (3), Failure to State a Cause of Action (4), Identity Theft
(6), and Wrong Party (7) are omitted, including Identity Theft from the previous
prototype. The overview identifies those omissions and directs users to clinic staff.
The preliminary section retains all 18 October 30 fields and its separate review.

Each defense starts under its own name and displays its November 7 explanation.
Defenses without screening branches put their checkbox question on that same page;
defenses with screening branches show the explanation separately before the questions. Selecting an answer immediately shows its approved response below the answer
controls, with the question and selection still visible. Changing the selection
replaces that response. Next records the answer and advances; previewing does not
write facts, choices, timestamps, or research events. Conditional response text is
removed from the following page, while independent checkbox guidance stays with
its question. In the SOL-only presentation demo, acknowledgments of payment-date or timing
answers appear inline immediately after radio selection. Checkbox-specific guidance
stays with each checkbox question: the main-defense eligibility explanation, combined
first/third guidance, and oral-contract second-box guidance. In SOL, second-checkbox information belongs to the following step, and “Confirm
selections” belongs to the review screen; neither appears as feedback to the
first/third checkbox choice. Ambiguity also keeps its explanation and checkbox question together, followed by
confirmation on a separate review screen. Mistake and Laches also confirm selections
on the following review. Other defenses retain the inline response behavior. Outcomes requiring several facts appear beside the last needed
question. Summaries retain the checklist and review evidence.

Choice responses are supplied with the page for immediate display. Text/date
questions that need a dynamic response use the read-only `/api/preview` endpoint;
stale requests are discarded. Next waits for a dynamic response, with a retry
control if it cannot load. Returning with Back or Change restores the response for
the displayed answer. Clarification chat can explain a draft response, which is
explicitly distinguished from confirmed case facts. Known preliminary facts are reused; unresolved fields return to their own
intake page when required. Users explicitly choose each offered checkbox. Unknown
answers stay separate from No, with clarification or clinic staff guidance when
the script supplies no other outcome. Staff referrals require explicit resolution.

Common Counts offers its first nested checkbox without an uncredited-payments
screen. Excuse offers its second and fifth nested checkboxes without additional
factual screening. Mitigation, Common Counts, and Excuse derive their main checkbox
from the user's nested choices. Their parent has no separate choice question.
Common Counts' fifth checkbox depends on the user's explicit Fraud selection;
its fourth checkbox is not offered because the Identity Theft defense is excluded.
Lack of Consideration can clarify suspected theft within its own screening when
recognition does not establish the required fact; this does not include or select
the excluded Identity Theft defense.

The language section asks whether the creditor **gave** the translated agreement;
a No can lead to an offer, while Yes finishes without one. A missing primary
language is collected before language-specific questions. No answer selects a
checkbox without an explicit choice, except the three parent boxes derived from
explicit nested selections as directed by the script.

Each section ends in its own summary or no-offer result page. The final review
shows all 17 defenses, nested options, selections, and unresolved questions. Case
details remain accessible throughout. Short answers and date/amount formats follow
the preliminary script. Browser progress is tab-local; the November 7 version uses
a new storage key to start a fresh review instead of importing an obsolete path.

## Script wording and formatting

The November 7 Word document governs both wording and user-facing paragraph/list
structure. `guided_script_formatting.yaml` records source paragraphs, Word list
levels, and the source document's SHA-256 fingerprint. Regenerate and verify it with:

```bash
.venv/bin/python scripts/extract_guided_script_formatting.py
.venv/bin/python scripts/extract_guided_script_formatting.py --check
```

The renderer uses structured paragraphs and semantic HTML lists for explanations,
checkbox guidance, inline responses, and approved clarification text. Source
paragraph breaks receive visible paragraph spacing; lists remain lists. Source
paragraph boundaries are also restored where an earlier copy folded them together.
Reviewer-outline bullets around an entire quoted reply are not presented as
user-facing list items. The source's actual lists inside quoted explanations are
preserved, including their separate groups. Text is inserted safely as text.

This formatting layer does not change the previously reviewed SOL/Ambiguity screen
boundaries, answers, or routing. Tests compare the generated metadata and all 17
defense introductions with the November 7 document.

## SOL screen placement

Preserve formatting when reading the Word source. Bold **Ask** instructions mark
questions; **If Yes/No/Not sure** instructions control the response to that
question; **Continue to** instructions move to a named step. Do not merge those
steps merely because deterministic routing can calculate their text immediately.

| Screen | Text before the choice | Inline after answering | Following step |
| --- | --- | --- | --- |
| Complaint payment date | Complaint date and timing comparison | Agreement or uncertainty acknowledgment | Personal timing question if needed; otherwise original-creditor result |
| Personal payment timing | Timing question | Matching Yes/No/Not sure acknowledgment | Original-creditor result |
| Main SOL checkbox | Debt-buyer explanation, or guidance beginning “Consider raising…” | Clarification only if undecided | First/third checkbox guidance |
| First/third checkbox decision | First/third checkbox explanation | Clarification only if undecided | Second-checkbox step; no second-box information or confirmation inline |
| Second-checkbox step, oral agreement | Oral-contract explanation and second checkbox question | Clarification only if undecided | Confirm selections |
| Second-checkbox step, written agreement | Explanation that the second checkbox does not apply | No checkbox offered | Confirm selections on the same review page |
| Confirm selections | Confirmation wording and checkbox checklist | No new checkbox decision | Next defense |

A recent original-creditor payment finishes without checkbox offers or selection
confirmation; its no-offer review remains available. Unresolved facts follow their
clarification routes. This map applies to the SOL presentation demo only.

## Ambiguity screen placement

The November 7 source groups the explanation with **Ask about this checkbox**,
then explicitly directs **Continue to “Confirm selections.”** Preserve these as
separate steps:

| Screen | Content | After answering |
| --- | --- | --- |
| Ambiguity checkbox | Full approved explanation and “Do you want to check off Ambiguity?” | Yes/No records the choice and advances; selection confirmation is not inline |
| Confirm selections | Selected/empty confirmation wording and Ambiguity checklist with Change | Continue to the next defense |

An undecided answer remains unresolved. Returning from clarification restores the
full explanation with the same checkbox question. Previews do not record a choice.

## Initial defense screens

Every defense starts with the defense name as its heading. For defenses without
screening branches (Ambiguity, Mistake, and Unconscionable Contract), the full
November 7 explanation and checkbox question appear in the body on that screen.
Word bullet lists and paragraph spacing are preserved.

Laches has a separate general-explanation screen, headed “Laches,” followed by
its screening questions. The explanation is not repeated on the checkbox screen.
Its selection confirmation remains on the following review.

Saved introduction records for combined screens remain replayable and are skipped
by Back. Saved Laches paths from the briefly combined layout also remain usable.

The shared script note applies only to defenses without screening branches:
**Show the general explanation and checkbox question together on one screen,
with the defense name as the heading.** Defenses with screening branches retain
their separate explanation screens before the follow-up questions.

## Editing and clarification

Back preserves answers. Change replays the updated path, retaining applicable
facts and explicit choices. Newly relevant questions require an answer. A removed
checkbox choice is discarded when its section reaches review and is not restored
if another edit later makes that checkbox available. Changing an earlier defense
also reconciles dependent offers in later defenses. Finishing after an edit requires
a fresh summary confirmation.

SOL retains its dependency planner, conditional timing evidence, and grouped first
and third choice. Names are used for personalization. Qualifying timing comparisons
can be reused without inventing agreement with an edited exact date. Irrelevant
unknown Laches facts do not block an offer supported by another Yes.

“Ask a question” uses the current approved page context and confirmed facts. Its
response always has `next_node_id: null`; chat does not answer form questions or
advance the guide. Approved explanations stay available if the model is unavailable.

## Implementation

`guided_defense_content.yaml` contains November 7 copy and route overrides.
`guided_sol.py` validates those overrides into a prototype-specific tree, renders
pages and clarification context from that tree, and replays validated histories.
The chatbot's canonical `interactive_tree.yaml` and its wording remain unchanged.
`guided_preliminary_fields.yaml` retains the October 30 intake. SOL's dependency
map remains in `sol_checkbox_dependencies.yaml` and `sol_dependency_map.py`.

`scripts/guided_clickthrough_demo.py` serves the form and clarification endpoints;
`scripts/assets/guided_sol/` contains the buildless browser assets. The progress
bar includes all sections and scrolls horizontally. The history limit accommodates
all 17 sections and clarification returns. `guided_collection.py` collects the
research datasets below. Tests cover source wording, allowed branches, full
traversal, no-offer outcomes, uncertainty, nested selections, editing, final review,
CSV collection, and non-advancing clarification.

The prototype performs no filing, document generation, Excel export, or account
storage. The deterministic form works without model calls; clarification chat uses
the configured model provider. Research records persist locally on the server.

## Debug section navigation

```bash
.venv/bin/python scripts/guided_clickthrough_demo.py --debug
```

Debug mode displays a banner and makes the scrollable section header clickable,
including Preliminary fields and all 17 defenses. Both the numbered circle and
section name activate the link; controls briefly disable while a page loads.
Versioned asset URLs ensure a refresh loads updated navigation code. A header jump fills unanswered
intake fields and starts that section directly, without answering or completing
skipped defenses. Click Preliminary fields to inspect or change the case details.
An already visited section in the current path can be revisited with its answers;
a new jump starts the selected section fresh using the current confirmed intake.

On the first debug visit, confirmed intake from the normal tab progress is copied
into separate debug storage. Existing answers and a valid current intake draft
are preserved. Missing values use the loaded example complaint where available;
remaining fallbacks are in `guided_debug.py`: an original creditor, both claim
types, $4,250, payment on March 15, 2021, filing on September 30, 2026, a recognized
account, a written agreement, and no debt-consolidation company. Both claim types
are used only when that field has not already been answered.

Advance, Back, Change, clarification, and reload work from the selected section.
The debug anchor is validated on every request. Header progress does not mark
skipped sections complete. Normal mode rejects debug jump requests and anchors.

Research collection is completely disabled in debug mode, including session start,
answer events, edits, and exit beacons. The debug server does not open or create
the research database or CSVs, even if a request includes collection metadata.
Normal browser progress and research files remain separate. Restart without
`--debug` to return to normal intake and collection.

## Research CSVs

Running the prototype without `--debug` automatically writes three UTF-8 CSVs to
`output/clickthrough/`. Use `--collection-dir PATH` to choose another directory.
All three use the requested variable names and share a random UUID `SESSION.ID`.
The defense names in column headers match the 17 IDs in `guided_sol.DEFENSES`.
The excluded defenses have no columns in new datasets. When an existing collection
directory contains records from an older prototype, exports preserve its historical
defense columns and rows alongside the new columns.

- `sessions.csv`: one row per session, including sessions abandoned in intake.
  Start time is the first successful page request. Completion becomes Yes only
  after Finish review reaches the final page; editing an answer requires fresh
  completion. Merely navigating Back does not undo completion. The tree version
  contains the source date and a content fingerprint of the scripts and rules.
- `defenses.csv`: one row per session, with three columns per defense. CHECKED is
  Yes if any box for that defense is selected. TREE.PROJECTION is Yes if at least
  one checkbox is offered on the current reconciled path, regardless of the user's
  choice. Both stay blank while unresolved. Projection becomes Yes when the tree
  reaches an offered checkbox, or No when the defense finishes without an offer.
  CHECKED becomes Yes on any explicit inclusion; it becomes No after all offered
  choices are explicitly declined, or the defense finishes without an offer.
  CHANGED is 1
  once a User change event edits a field belonging to that defense.
  Shared preliminary edits count for the defenses that use those fields: creditor
  type for SOL, Fraud, and Waiver; claim type for Common Counts and Excuse;
  consolidation for Mitigation, Rescission, and Accord; recognition for Lack of
  Consideration; and opening date for Capacity. Independent preliminary fields and
  personalization-only names do not set a defense's CHANGED flag.
- `responses.csv`: an append-only event dataset. Preliminary item IDs use the
  field identifiers from `guided_preliminary_fields.yaml`, such as `CASE.NUMBER`,
  `PLAINTIFF`, and `COMPLAINT.DATE` (the filing date). Defense questions and deterministic conditions
  use their tree node IDs. Derived original-creditor values and calculated
  `DEFENSE.<name>.CHECKED` / `TREE.PROJECTION` values are also recorded. Answers
  use their stored values (for example `yes`, `no`, `unknown`, or an ISO date).
  Each calculated field first appears only when its own result is determined.
  TREE.PROJECTION is recorded when the tree reaches a checkbox offer or completes
  a no-offer path. CHECKED is recorded after an explicit inclusion, after all
  offered choices are declined, or on completion of a no-offer path. A first No
  on the main SOL checkbox does not determine CHECKED while indented choices
  remain unanswered. Starting a defense, incomplete screening, and uncertain
  checkbox answers do not create negative results. The defense CSV retains its
  one-row-per-session shape, with blank unresolved values.

The response columns, in order, are `SESSION.ID`, `RESPONSE.ITEM.ID`,
`RESPONSE.ITEM.VALUE`, `RESPONSE.EVENT.TYPE`, `RESPONSE.REVISION.NUMBER`,
`RESPONSE.START.TIME`, `RESPONSE.CHECK.TIME`, and `RESPONSE.END.TIME`.
The four event types are First submission, User change, Program calculation,
and Program invalidation. `RESPONSE.CALC.OR.INPUT` is no longer exported;
the event type identifies who produced the value.

Each item's first recorded value has revision 0; every subsequent change or
invalidation increments that item's revision independently. A Program invalidation
has an empty value. A new explicit answer after invalidation is a User change
event. Valid retained answers do not
produce duplicate submissions. Pending replay of a later defense is not treated
as invalidation. Back, opening Change, submitting an unchanged answer, navigation
screens, and clarification-chat messages do not create answer events.
If an edit makes a previously known defense result unresolved, the response log
records a Program invalidation and the defense CSV clears that field until a
new result is determined. Previously collected rows retain their original
values and timestamps; the new collection version starts a fresh browser review.

User response start time comes from when the browser renders that question.
Check time is the most recent answer selection or valid text/date/amount entry
on that page; end time comes from the click submitting it. Check time is NA if
the user accepts a prefilled value without interacting with the answer control.
These timestamps use the browser clock, normalized to UTC. Check time, when
present, must fall between start and end. Program calculations and invalidations
use the server clock and equal start/end times because they have no user display
interval; their check time is always NA. Session timestamps also use the server
clock. Unsubmitted drafts are not collected.

Start over ends the current session and creates a new UUID without deleting its
records. Closing or leaving the page sends a browser `pagehide` beacon to record
the end time. Reloading/restoring that tab keeps its UUID and clears the end time
while the session is active again. Browser shutdown, crashes, or a disconnected
server can prevent the exit beacon arriving; in that case SESSION.END.TIME stays
empty. Completion remains independently recorded even if exit reporting fails.

`collection.sqlite3` in the same directory is the authoritative local store.
Each accepted operation commits there before atomically replacing each CSV;
server startup rebuilds the CSVs from the database. Repeated delivery of the
same collection event ID is ignored. Use one prototype server per collection
directory. The `output/` directory is gitignored; Start over clears browser
progress but does not erase the collected CSVs or database.
