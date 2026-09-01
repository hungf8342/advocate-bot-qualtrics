# Advocate Bot Qualtrics — Agent Guide

## Environment and common commands

This repository uses a local virtual environment at `.venv/`. It is intentionally
gitignored. Do not rely on activating it: agent command sessions may be fresh
shells. Use its interpreter explicitly instead.

Create the environment and install development/demo dependencies (once per
checkout):

```bash
python -m venv .venv
.venv/bin/python -m pip install -e ".[dev,demo]"
```

Use these commands for normal work:

```bash
.venv/bin/python -m pytest
.venv/bin/python scripts/extract_complaint_to_json.py
.venv/bin/python scripts/interactive_chat_demo.py
.venv/bin/python scripts/run_interactive_simulator.py
```

For an interactive human terminal only, activation remains optional:

```bash
source .venv/bin/activate
```

## Scope

- This repository uses two decision-tree modes:
  - Interactive: user-driven progression via `process_chat(...)`
  - Autonomous: AI-driven progression from `ComplaintFactSheet` JSON

## Data contract

- `ComplaintFactSheet` is fact-only (`schema_version: "1.1"`).
- Do not reintroduce defense judgment fields into extraction output.
- Defense analysis belongs in decision-tree logic, not extraction.

## LLM output requirements

- Interactive chat responses must remain structured with:
  - `user_intent`
  - `assistant_reply`
  - `next_node_id`
- `next_node_id` must match one of the current node's branch IDs when advancing.
- If intent is not an answer to the node question, `next_node_id` must be `null`.

## Repository safety

- Never commit `.env`.
- Never commit generated files in `output/`.
- Keep `.env.example` secret-free.

## Testing

- Add or update tests whenever node schemas, routing validation, or prompts change.
- Ensure autonomous traversal tests cover:
  - valid branch constraints
  - terminal-node completion
  - summary/open-questions output
