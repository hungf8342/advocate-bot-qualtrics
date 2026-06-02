# advocate-bot-qualtrics

Extract structured facts from legal complaints (`ComplaintFactSheet`) via Anthropic structured outputs, for use as input to a Python decision tree.

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
fdcpa = data["fdcpa"]["applies_or_alleged"]  # bool or null
amount = data["amount_sued_for"]             # string decimal, e.g. "953.10"
```

### Tree field cheat sheet

| JSON path | Type in JSON | Notes |
|-----------|--------------|--------|
| `schema_version` | string | `"1.0"` |
| `plaintiff_names` | array of strings | Empty if none |
| `defendant_names` | array of strings | Empty if none |
| `jurisdiction` | string or null | |
| `amount_sued_for` | string or null | Decimal as string |
| `date_complaint_filed` | string or null | ISO date; complaint “Dated:” line |
| `alleged_incident_date` | string or null | Often charge-off or breach date |
| `date_user_failed_to_pay` | string or null | Last payment / default if stated |
| `causes_of_action` | array of strings | |
| `statute_of_limitations` | string or null | Free text if not a single date |
| `failure_to_state_a_claim_*` | bool/string or null | Assessment fields — advisory |
| `original_contract_included` | bool or null | null = not stated |
| `payment_or_balance_log_included` | bool or null | |
| `bill_of_assignment_or_debt_ownership_evidence` | bool or null | |
| `fdcpa.applies_or_alleged` | bool or null | |
| `fdcpa.allegations` | array of strings | |
| `fdcpa.punishment_threatened` | string or null | |
| `amount_inconsistent_with_case` | string or null | |
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
