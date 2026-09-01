# Advocate Bot Qualtrics

This is a confidential, user-entered consumer-debt decision-tree chatbot. It does not accept, upload, parse, or store complaint documents. The chat begins by asking the user for the plaintiff, amount sought, complaint date, and last payment date; those values are kept in the active session for the tree.

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

The declarative consumer-debt tree is in [`interactive_tree.yaml`](src/advocate_bot_qualtrics/practice_areas/consumer_debt/interactive_tree.yaml). Its initial nodes collect:

- plaintiff name;
- amount sought;
- complaint date; and
- last payment date.

The host validates and stores dates in the in-memory session, then performs deterministic SOL and FDCPA screening steps. The LLM only classifies the user’s answer against the current node; it cannot advance to a branch outside the node’s declared branch IDs.

## Tests

```bash
.venv/bin/python -m pytest
```
