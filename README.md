# Advocate Bot Qualtrics

This is a confidential consumer-debt decision-tree chatbot. It accepts fact-only preliminary fields from a separate complaint scraper, asks litigants to verify them, and then presents the nine affirmative defenses covered by the explanation documents. Parsed values and litigant corrections are kept in the active session. Complaint scraping itself is handled outside this application.

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

To try the preliminary verification flow with an imaginary complaint:

```bash
.venv/bin/python scripts/interactive_chat_demo.py --complaint-fields examples/complaints/original-creditor.json
```

Use `examples/complaints/debt-buyer.json` for a debt-buyer example with missing dates.
The temporary JSON format and programmatic entry point are documented in
[the sample input guide](examples/complaints/README.md). Without an input file,
parsed fields are shown as unknown and can be filled through the correction questions.

For debugging, add `--debug-shortcuts` and type **I agree with all** during
preliminary intake to accept remaining parsed fields and continue to defenses.
This option is off by default. Prior answers and corrections are retained;
unanswered recognition, oral-agreement, and consolidation questions stay unknown.
Synthetic confirmations are marked in the developer snapshot.

The demo has no file-upload control. Do not use its public-share option with real client information.

## Interactive flow

The declarative consumer-debt tree is in [`interactive_tree.yaml`](src/advocate_bot_qualtrics/practice_areas/consumer_debt/interactive_tree.yaml). Preliminary Questions display approved explanations and ask whether the litigant agrees with each parsed field. A "No" asks for their preferred value; there is one agreement question per field. Account recognition, oral agreement, and debt consolidation remain direct questions. The sidebar shows all parsed fields before verification and labels their verification status. Ownership assertions and attached ownership evidence are separate fields.

The host (the Python conversation engine) reuses verified answers and preferred values, follows the YAML branches, and computes internal screening assessments. Original parsed values remain available for reference and complaint-presence checks. The complaint filing date is verified after the account-opening date and used without asking again. Original-creditor SOL screening asks the litigant to confirm the complaint's payment-to-filing estimate, or answer whether payment was less than a year before filing. The clinic screen explains preservation for a year or more, uncertainty, or a debt-buyer plaintiff. This one-year screen is separate from the legal filing deadline. The litigant decides whether to include the defense.

The LLM classifies answers and generates help and final Q&A responses. The host validates routing against the current node's declared branch IDs and displays approved node explanations. The first nine defenses integrate the updated October explanations: statute of limitations, ambiguity, standing/privity, failure to state a cause of action, mistake, identity theft, wrong party, laches, and fraud/misrepresentation/concealment. Each subsection shows a heading, general explanation, known facts, applicable questions, and personalized explanation. Every defense then asks whether the litigant wants to check it off. An uncertain answer offers clarification and stays on that defense until the litigant chooses. Relevant questions receive focused answers grounded in the approved text and recorded facts; unrelated questions are redirected. The final review recaps the litigant's own choices and clinic referrals, without announcing computed checkbox statuses.

The two explanation documents are the sources for the YAML content and routing.
Document IF branches evaluate intake facts silently. Ambiguity and Mistake contain
only general explanations, so each leads directly to the litigant's selection.
The flow ends after the ninth defense; the basic decision tree is retained as a reference document.

Preliminary questions have headings, and conditional explanation paragraphs retain
their original document positions. The [affirmative-defense integration review](docs/affirmative-defense-integration-review.md)
preserves the earlier planning discussion. See [the current flow documentation](docs/decision-tree.md)
for the implemented rules and subsequent user decisions.

## Project structure

- `src/advocate_bot_qualtrics/core/`: reusable conversation engine, chat validation, node schemas, and shared utilities.
- `src/advocate_bot_qualtrics/practice_areas/consumer_debt/`: YAML tree, session fields, field reuse, defense screening, rendering, and export mapping.
- `src/advocate_bot_qualtrics/llm/`: structured model calls.
- `prompts/`: chat instructions and confidence calibration.
- `scripts/`: local demo and its UI assets.
- `tests/`: automated routing, intake, screening, Q&A, presentation, and export checks.

The former `advocate_bot_qualtrics.decision_tree` compatibility package has been removed; use the canonical modules above. The package-level `process_chat` import remains available. The current source documents are in `docs/source-material/2026-10-11/`.

See [decision-tree structure and field reuse](docs/decision-tree.md) for editing guidance. Restart the demo after changing YAML or Python, then refresh the browser to start a new session.

## Tests

```bash
.venv/bin/python -m pytest
```
