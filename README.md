# advocate-bot-qualtrics

Extract structured facts from legal complaints (`ComplaintFactSheet`) via Anthropic or OpenAI structured outputs, for use as input to downstream logic (e.g. a decision tree).

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # add ANTHROPIC_API_KEY or OPENAI_API_KEY
```

## Usage

```python
from advocate_bot_qualtrics import extract_complaint_facts

facts = extract_complaint_facts(open("complaint.txt").read())
print(facts.model_dump_json(indent=2))
```

## TODO (later)

- [ ] **One-time JSON for decision tree** — Run extraction once on the sample (or real) complaint and save `output/complaint_fact_sheet.json`. The decision tree should read that file only; it does not need the LLM or API keys on each run.
  1. Set API keys in `.env` (see `.env.example`).
  2. `python scripts/extract_complaint_to_json.py`
  3. Point the decision tree at `output/complaint_fact_sheet.json`.

Optional: commit a golden JSON only after reviewing extraction quality (not required for the tree to work locally).

## Tests

```bash
pytest
```
