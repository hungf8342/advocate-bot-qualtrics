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
.venv/bin/python scripts/guided_clickthrough_demo.py
```

For an interactive human terminal only, activation remains optional:

```bash
source .venv/bin/activate
```

## Scope

- The clickthrough prototype is the application to use and build on. Its entry
  point is `scripts/guided_clickthrough_demo.py`, its UI is in
  `scripts/assets/guided_sol/`, and its workflow is in
  `practice_areas/consumer_debt/guided_sol.py`.
- The old conversation-driven chatbot (`core/process_chat.py`, `core/engine.py`,
  and `scripts/interactive_chat_demo.py`) is legacy code slated for retirement.
  Do not add features there. See `docs/chatbot-retirement-audit.md` before deleting
  modules: the clickthrough still uses shared tree, session, and defense logic.
- Consumer-debt questions and routing use `interactive_tree.yaml` plus the
  `guided_*.yaml` content/layout files. Screening rules remain in
  `affirmative_defenses.py` in the same practice-area directory.
- The old `decision_tree/` compatibility package has been removed. Use canonical
  `core/` and practice-area imports.
- Document extraction, autonomous fact-sheet traversal, and the simulator are
  not present in this checkout.

## Data contract

- Case facts come from user answers. Clickthrough requests replay answer history
  into a session; normal mode collects research records through
  `guided_collection.py` in SQLite with CSV exports. Debug mode disables collection.
- The clickthrough filing-date field is `COMPLAINT.DATE`, bound to
  `session.filing_date`, then used directly by SOL screening.
- Defense analysis belongs in practice-area decision logic. If document
  extraction is restored, keep its output fact-only; do not add defense judgments
  to `ComplaintFactSheet` (`schema_version: "1.1"`).

## LLM output requirements

- Clickthrough clarification-chat responses must remain structured with:
  - `user_intent`
  - `assistant_reply`
  - `next_node_id`
- Clarification chat must not record answers or advance the clickthrough;
  `next_node_id` must be `null` in its API response.
- While the legacy chatbot remains, its advancing responses must use a current
  branch ID; non-answer responses must have `next_node_id: null`.

## Repository safety

- Never commit `.env`.
- Never commit generated files in `output/`.
- Keep `.env.example` secret-free.

## Testing

- Add or update tests whenever node schemas, routing validation, or prompts change.
- Ensure clickthrough tests cover:
  - valid branch constraints
  - terminal-node completion
  - summary/open-questions output
  - edits, retained answers, and invalidations
  - research collection and debug-mode isolation
