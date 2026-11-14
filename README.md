# Advocate Bot Qualtrics

A guided consumer-debt clickthrough with one question per page, Back and Change
controls, defense summaries, an optional clarification chat, and research data
collection. The clickthrough is the application to use and build on.

## Setup

Use Python 3.11 or newer. Create the local environment and install dependencies:

```bash
python -m venv .venv
.venv/bin/python -m pip install -e ".[dev,demo]"
```

Run commands with the virtual environment's interpreter; activation is optional.
On Windows, use `.venv\Scripts\python.exe` instead of `.venv/bin/python`.

The form and data collection work without a model key. For the optional
clarification chat, create a local `.env` using `.env.example` and set
`ZAI_API_KEY`. Only `CHAT_PROVIDER=zai` is supported. Never commit `.env`.

## Run the clickthrough

```bash
.venv/bin/python scripts/run_clickthrough.py
```

Open <http://localhost:7861/>. The fictional original-creditor example supplies
prefilled intake values; those values become recorded facts only when submitted.
To use a debt-buyer example or start with blank fields:

```bash
.venv/bin/python scripts/run_clickthrough.py --complaint-fields examples/complaints/debt-buyer.json
.venv/bin/python scripts/run_clickthrough.py --blank
```

The [example input guide](examples/complaints/README.md) describes the fact-only
JSON format. The application has no document upload or extraction feature.

For review and development:

```bash
.venv/bin/python scripts/run_clickthrough.py --debug
```

Debug mode enables clickable section headers and example defaults for unanswered
intake fields. It uses separate browser progress and **disables research collection**.
Run without `--debug` when collecting research results.

## Scope and data

The guide follows the November 10 scripts for 17 defenses: 1, 2, 5, 8, and 9–21.
Standing/Privity, Failure to State a Cause of Action, Identity Theft, and Wrong
Party are excluded. Preliminary intake follows the October 30 fields script.
Facts determine which choices are offered; only explicit user choices select
checkboxes. Unknown answers remain distinct from No.

Back preserves answers. Change reconciles the revised path, retains applicable
answers, and revisits dependent questions. The final review includes all 17
defenses, nested choices, and unresolved questions. Clarification chat explains
the current page; it cannot record answers or advance the guide.

Normal mode stores research records in `output/clickthrough/collection.sqlite3`
and exports `sessions.csv`, `defenses.csv`, and `responses.csv`. SQLite is the
authoritative store; records persist across server restarts. Use
`--collection-dir PATH` to change the destination and one server process per
collection directory. Keep research data out of Git. Browser progress is tab-local;
there is no account sign-in or cross-device resume.

See the [clickthrough guide](docs/clickthrough-guide.md) for screen behavior,
debug mode, data definitions, and browser-exit timing limitations.

## Implementation

- `scripts/run_clickthrough.py`: FastAPI entry point and API routes.
- `scripts/assets/clickthrough/`: buildless HTML, CSS, and JavaScript interface.
- `src/advocate_bot_qualtrics/practice_areas/consumer_debt/workflow.py`: replay,
  page rendering, edits, and traversal.
- `defense_content.yaml`, `intake_fields.yaml`, `screen_layout.yaml`, and
  `script_formatting.yaml`: current wording, intake, layout, and formatting.
- `base_tree.yaml` and `base_tree.py`: shared base tree used by guided overrides
  and answer bindings. Historical node IDs remain stable for saved histories.
- `affirmative_defenses.py`, `session.py`, `preliminary.py`, `rendering.py`, and
  `sol_dependency_map.py`: shared rules, facts, text substitution, and dependencies.
- `research_collection.py`: durable research collection and CSV exports.
- `core/`: shared node/response schemas, tree validation, and error types.
- `llm/` and `prompts/clickthrough_clarification.md`: optional clarification.
- `docs/source-material/`: approved Word documents and source history. Current
  defense wording comes from `2026.11.10/`; intake comes from `2026-10-30/`.

The conversation-driven chatbot, Gradio interface, confidence scoring, and Excel
export have been removed. Their pre-removal snapshot is Git commit `b7a72b0`.
Base-tree nodes and source documents remain where needed by validation, replay,
shared rules, and provenance tests. Do not prune them solely because they are not
shown as clickthrough pages.

## Verification

```bash
.venv/bin/python -m pytest
.venv/bin/python scripts/extract_script_formatting.py --check
```

Tests cover allowed branches, complete traversal, summaries/open questions,
intake, uncertainty, explicit selections, edits and invalidations, debug isolation,
research collection, source wording/formatting, and non-advancing clarification.
Restart the server after Python or YAML changes and refresh the browser. Changes
to collection-fingerprinted sources change the recorded tree version; preserve
historical data when updating the application.
