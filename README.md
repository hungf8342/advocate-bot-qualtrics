# Advocate Bot Qualtrics

This is a confidential, user-entered consumer-debt decision-tree chatbot. It does not accept, upload, parse, or store complaint documents. The chat collects Preliminary Questions from the clinic draft, then screens 21 affirmative defenses using those answers. Values and user corrections are kept in the active session.

## Setup

```bash
python -m venv .venv
.venv/bin/python -m pip install -e ".[dev,demo]"
```

Set `ZAI_API_KEY` in `.env` for the interactive chat model. Never commit `.env`.

## Run the local demo

```bash
.venv/bin/python scripts/interactive_chat_demo.py
```

The demo has no file-upload control. Do not use its public-share option with real client information.

## Interactive flow

The declarative consumer-debt tree is in [`interactive_tree.yaml`](src/advocate_bot_qualtrics/practice_areas/consumer_debt/interactive_tree.yaml). Preliminary Questions collect the plaintiff, account recognition, law firm, complaint filing date, claim type, oral/written agreement, amount, dates, attachments, verification, and debt consolidation status. Disputed amounts and dates are replaced with the user's corrections for later use; the original complaint entries remain available for questions about what the complaint contains.

The host (the Python conversation engine) reuses tagged answers, follows the YAML branches, and computes defense results. The complaint filing date is collected after the law-firm question, displayed in the case details, and used for SOL screening without asking again. Unknown filing dates leave date-dependent SOL screening unresolved for clinic review.

The LLM classifies answers and generates help and final Q&A responses. The host validates routing against the current node's declared branch IDs and displays approved node explanations when available. The final review lists checked, unchecked, and unresolved defenses. Conditional scripted explanations and an approved library for other questions are planned; they are not implemented yet.

## Project structure

- `src/advocate_bot_qualtrics/core/`: reusable conversation engine, chat validation, node schemas, and shared utilities.
- `src/advocate_bot_qualtrics/practice_areas/consumer_debt/`: YAML tree, session fields, field reuse, defense screening, rendering, and export mapping.
- `src/advocate_bot_qualtrics/llm/`: structured model calls.
- `prompts/`: chat instructions and confidence calibration.
- `scripts/`: local demo and its UI assets.
- `tests/`: automated routing, intake, screening, Q&A, presentation, and export checks.

The former `advocate_bot_qualtrics.decision_tree` compatibility package has been removed; use the canonical modules above. The package-level `process_chat` import remains available. The simulator remnants, sample fact-sheet fixture, and older `Tree-Structures.docx` draft have also been removed. The current source draft is `Decision Tree Draft 9_24_2026.docx`.

See [decision-tree structure and field reuse](docs/decision-tree.md) for editing guidance. Restart the demo after changing YAML or Python, then refresh the browser to start a new session.

## Tests

```bash
.venv/bin/python -m pytest
```
