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

The declarative consumer-debt tree is in [`interactive_tree.yaml`](src/advocate_bot_qualtrics/practice_areas/consumer_debt/interactive_tree.yaml). Preliminary Questions collect the plaintiff, account recognition, law firm, claim type, oral/written agreement, amount, dates, attachments, verification, and debt consolidation status. Disputed amounts and dates are replaced with the user's corrections for later use; the original complaint entries remain available for questions about what the complaint contains.

The host reuses tagged answers, follows the YAML branches, and computes defense results. The LLM only classifies the user’s answer against the current node; it cannot advance to a branch outside the node’s declared branch IDs. The final review lists checked, unchecked, and unresolved defenses.

See [decision-tree structure and field reuse](docs/decision-tree.md) for editing guidance. Restart the demo after changing YAML or Python, then refresh the browser to start a new session.

## Tests

```bash
.venv/bin/python -m pytest
```
