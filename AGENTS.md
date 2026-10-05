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
.venv/bin/python scripts/interactive_chat_demo.py
```

For an interactive human terminal only, activation remains optional:

```bash
source .venv/bin/activate
```

## Scope

- The current application is interactive: user-driven progression via
  `core/process_chat.py` and `core/engine.py`.
- Consumer-debt questions and routing live in
  `practice_areas/consumer_debt/interactive_tree.yaml`; screening rules live in
  `affirmative_defenses.py` in the same directory.
- The old `decision_tree/` compatibility package has been removed. Use canonical
  `core/` and practice-area imports.
- Document extraction, autonomous fact-sheet traversal, and the simulator are
  not present in this checkout.

## Data contract

- Case facts come from user answers and live in the active session.
- The complaint filing date is collected in preliminary intake as `FILING-DATE`
  and `session.filing_date`, then used directly by SOL screening.
- Defense analysis belongs in practice-area decision logic. If document
  extraction is restored, keep its output fact-only; do not add defense judgments
  to `ComplaintFactSheet` (`schema_version: "1.1"`).

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
- Ensure engine traversal tests cover:
  - valid branch constraints
  - terminal-node completion
  - summary/open-questions output
