# advocate-bot-qualtrics

Extract structured **factual** allegations from legal complaints (`ComplaintFactSheet`) via Anthropic structured outputs. Defense analysis (statute of limitations, FDCPA, failure to state a claim) belongs in your decision tree, not in this JSON.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
# Edit .env: set ANTHROPIC_API_KEY (Anthropic only; OpenAI optional)
```

Default model: `claude-sonnet-4-6` (override with `ANTHROPIC_MODEL` in `.env`).

## One-time JSON extraction

Run once per complaint. The decision tree reads JSON only — no API key on each tree run.

```bash
python scripts/extract_complaint_to_json.py
# Default: knowledge-base/1 - Complaint.pdf → output/complaint_fact_sheet.json
```

Re-run when you have a new complaint or change the schema/prompt.

## Decision tree chat (`process_chat`)

After you have a `ComplaintFactSheet` JSON saved, the chat engine uses the extracted facts to help classify the user's message at the current node and advance via `next_node_id`.

`process_chat` signature is:

`process_chat(user_message, current_node, fact_sheet)`

Notes:
- `user_message` may include a short host-prepared transcript of recent turns (and the latest user text). `process_chat` itself is stateless.
- If the LLM decides `user_intent="answer_node"`, `next_node_id` must match one of the provided `current_node.branches[*].branch_id` values.

Example:

```python
from advocate_bot_qualtrics.decision_tree import process_chat, CurrentNode, TreeBranch
from advocate_bot_qualtrics.fact_sheet_io import load_complaint_fact_sheet

facts = load_complaint_fact_sheet("output/complaint_fact_sheet.json")

node = CurrentNode(
    node_id="n1",
    question="Did the complaint plead the last payment date?",
    branches=[
        TreeBranch(branch_id="yes", label="Yes"),
        TreeBranch(branch_id="no", label="No / unknown"),
    ],
)

reply = process_chat("User: It says last payment was 12/23/2020", node, facts)
print(reply.user_intent, reply.next_node_id)
```

## Two decision-tree versions

This repo now includes two separate decision-tree flows:

1. **Interactive tree** (user-driven): `process_chat(user_message, current_node, fact_sheet)`
2. **Autonomous tree** (AI-driven from JSON facts): `process_autonomous(fact_sheet, start_node, tree_map)`

Interactive mode asks/handles user turns per node. Autonomous mode traverses the tree directly from `ComplaintFactSheet` values and ends by inviting user questions.

Interactive tree flow (SOL then FDCPA, per `Tree-Structures.docx`):

1. Start at `INTERACTIVE_TREE[INTERACTIVE_START_NODE_ID]` (`confirm_filing_date`).
2. Seed `InteractiveSessionState` with `init_session_from_fact_sheet(facts)`.
3. On each user turn, call `process_chat` unless the current node is a hook (`sol_computation`, `fdcpa_computation`).
4. After `user_intent="answer_node"`, update session and resolve the next node:

```python
from advocate_bot_qualtrics.decision_tree import (
    INTERACTIVE_START_NODE_ID,
    INTERACTIVE_TREE,
    apply_interactive_branch,
    advance_from_hook,
    init_session_from_fact_sheet,
    is_interactive_hook_node,
    process_chat,
    resolve_interactive_next_node,
)

session = init_session_from_fact_sheet(facts)
current_node = INTERACTIVE_TREE[INTERACTIVE_START_NODE_ID]

if is_interactive_hook_node(current_node.node_id):
    # Host runs SOL/FDCPA logic (see interactive_computations.py), then:
    next_id = advance_from_hook(current_node.node_id)
else:
    turn = process_chat(user_message, current_node, facts)
    if turn.user_intent == "answer_node" and turn.next_node_id:
        parsed_date = host_parse_date(user_message)  # on submit branches
        apply_interactive_branch(
            session, current_node.node_id, turn.next_node_id, submitted_date=parsed_date
        )
        next_id = resolve_interactive_next_node(
            current_node.node_id, turn.next_node_id, session
        )
```

Static branch wiring lives in `INTERACTIVE_ROUTES`; `contact_third_parties` uses session flags to skip the evidence question when neither arrest threats nor third-party disclosures were reported.

If the user disputes a filing or last-payment date from the complaint, the tree first asks whether they may be looking at a different complaint; otherwise it collects a corrected date. Session flags `filing_date_changed` and `last_payment_date_changed` track user corrections (for future export/dataframe work).

Per-node answer confidence (0–100) is stored in session when the user advances the tree. Scoring rules live in [`prompts/confidence_scoring_calibration.md`](prompts/confidence_scoring_calibration.md). Pure "I don't know" responses skip the current question via host routing; hedged answers ("I think yes") still route and may show a one-sentence hedge when confidence is below `CONFIDENCE_HEDGE_THRESHOLD` (default 70)—the LLM writes the hedge when valid, otherwise the host uses a generic fallback.

When the interactive tree completes, field values and confidence scores append as one row to `output/session_fields.xlsx` (override with `SESSION_FIELDS_XLSX_PATH`). User-corrected complaint filing or last-payment dates are capped below 70% confidence in the export.

> Placeholder status: current tree definitions are scaffolding only and have **not** been fully reviewed/finalized for legal correctness yet. Validate node logic and branch criteria before production use.

### Interactive chat demo (browser)

Local Gradio UI for live testing the full interactive tree against pre-extracted JSON facts.

```bash
pip install -e ".[demo]"
python scripts/interactive_chat_demo.py
python scripts/interactive_chat_demo.py --facts-json output/complaint_fact_sheet.json
```

| Flag | Notes |
|------|--------|
| `--facts-json` | Defaults to `fixtures/complaint_fact_sheet.sample.json` |
| `--share` | Creates a **public URL** — dev demos only; do not use with real client data |
| `--host` / `--port` | Bind address (default `127.0.0.1:7860`) |

Requires `ANTHROPIC_API_KEY` in `.env`. The API key stays server-side; never commit `.env`.

The demo uses one in-memory `InteractiveChatEngine` per process (single-user). Multi-user hosting should wrap the same engine in FastAPI with per-session state. SOL hook logic uses a **1095-day demo threshold**, not calendar-year legal analysis.

Core host logic lives in `advocate_bot_qualtrics.decision_tree.interactive_host` (`InteractiveChatEngine`) and is reusable outside Gradio.

### Autonomous mode example

```python
from advocate_bot_qualtrics.decision_tree import (
    AUTONOMOUS_START_NODE_ID,
    AUTONOMOUS_TREE,
    process_autonomous,
)
from advocate_bot_qualtrics.fact_sheet_io import load_complaint_fact_sheet

facts = load_complaint_fact_sheet("output/complaint_fact_sheet.json")
start_node = AUTONOMOUS_TREE[AUTONOMOUS_START_NODE_ID]

result = process_autonomous(facts, start_node, AUTONOMOUS_TREE)
print(result.summary)
print(result.open_questions_prompt)
```

## Load JSON in your decision tree

```python
from pathlib import Path
from advocate_bot_qualtrics.fact_sheet_io import load_complaint_fact_sheet

facts = load_complaint_fact_sheet("output/complaint_fact_sheet.json")
# Or committed sample: fixtures/complaint_fact_sheet.sample.json

if facts.date_complaint_filed is None:
    ...
```

Raw dict access (same file, no Pydantic):

```python
import json
data = json.loads(Path("fixtures/complaint_fact_sheet.sample.json").read_text())
filed = data["date_complaint_filed"]       # "YYYY-MM-DD" or null
incident = data["alleged_incident_date"]
default_date = data["date_user_failed_to_pay"]
amount = data["amount_sued_for"]             # string decimal, e.g. "953.10"
```

### Tree field cheat sheet

| JSON path | Type in JSON | Notes |
|-----------|--------------|--------|
| `schema_version` | string | `"1.1"` |
| `plaintiff_names` | array of strings | Empty if none |
| `defendant_names` | array of strings | Empty if none |
| `jurisdiction` | string or null | |
| `amount_sued_for` | string or null | Decimal as string |
| `date_complaint_filed` | string or null | ISO date; complaint “Dated:” line |
| `alleged_incident_date` | string or null | Often charge-off or breach date |
| `date_user_failed_to_pay` | string or null | Last payment / default if stated |
| `causes_of_action` | array of strings | |
| `original_contract_included` | bool or null | null = not stated |
| `payment_or_balance_log_included` | bool or null | |
| `bill_of_assignment_or_debt_ownership_evidence` | bool or null | |
| `amount_inconsistent_with_case` | string or null | Factual amount contradictions only |
| `field_citations` | object | Audit only — skip in tree v1 |

**Null semantics:** `null` means not stated in the complaint (not “no”). Do not treat null booleans as `false`.

### Review checklist (sample complaint)

After extraction, spot-check against the PDF:

- [ ] Plaintiff / defendant names
- [ ] `amount_sued_for` vs prayer for relief
- [ ] `date_complaint_filed` vs “Dated:” on complaint
- [ ] `date_user_failed_to_pay` vs last payment date
- [ ] `alleged_incident_date` (charge-off vs overdue — confirm intent for your tree)
- [ ] `causes_of_action`
- [ ] Exhibit / assignment flags

Sample PDF run (reviewed): parties, $953.10, filed 2025-09-30, last payment 2020-12-23, charge-off 2022-08-24 — match [`fixtures/complaint_fact_sheet.sample.json`](fixtures/complaint_fact_sheet.sample.json).

## Programmatic extraction

```python
from advocate_bot_qualtrics import extract_complaint_facts

facts = extract_complaint_facts(open("complaint.txt").read())
print(facts.model_dump_json(indent=2))
```

## Tests

```bash
pytest
```

## Git

- Commit: `.env.example`, `fixtures/`, code, README
- Never commit: `.env`, `output/` (gitignored)
