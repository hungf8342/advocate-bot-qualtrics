# Advocate Bot Qualtrics

This is a confidential consumer-debt decision-tree chatbot. It accepts fact-only preliminary fields from a separate complaint scraper, asks litigants to verify them, and then presents the 21 affirmative defenses in the October 25 conversation scripts. Parsed values and litigant corrections are kept in the active session. Complaint scraping itself is handled outside this application.

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

## Guided click-through prototype

A separate interface presents one question per page with Back and Next controls,
a payment timeline, a clarification chat window, and a summary for each defense.
It follows the October 30 script for Statute of Limitations, Ambiguity, Identity
Theft, and Laches (defenses 1, 2, 6, and 8). Editing
a field preserves independent answers and revisits only questions that could
affect the checkbox choices:

Preliminary fields form their own section, using all 18 fields in the October 30
preliminary-fields script. Defenses reuse those recorded fields and ask only
additional questions; unresolved fields return to the preliminary section.

```bash
.venv/bin/python scripts/guided_clickthrough_demo.py
```

Open <http://localhost:7861/>. The original-creditor example is prefilled for review.
Use `--complaint-fields examples/complaints/debt-buyer.json` for the debt-buyer path,
or `--blank` to start with blank fields. This prototype runs independently of the
chatbot on port 7860 and stops after Laches, with a final review of all four defenses.

The mini chat uses the existing `.env` model configuration and only explains the
current page. It never records answers or advances the review. See the
[guided prototype guide](docs/guided-sol-prototype.md) for behavior and limitations.

## Interactive flow

The declarative consumer-debt tree is in [`interactive_tree.yaml`](src/advocate_bot_qualtrics/practice_areas/consumer_debt/interactive_tree.yaml). Preliminary Questions display approved explanations and ask whether the litigant agrees with each parsed field. A "No" asks for their preferred value; there is one agreement question per field. Account recognition, oral agreement, and debt consolidation remain direct questions. The sidebar shows all parsed fields before verification and labels their verification status. Ownership assertions and attached ownership evidence are separate fields.

The host (the Python conversation engine) reuses verified answers and preferred values, follows the YAML branches, and evaluates the scripts’ factual conditions. Original parsed values remain available for reference and complaint-presence checks. The complaint filing date is verified after the account-opening date and used without asking again. Original-creditor SOL screening asks the litigant to confirm the complaint's last-payment date, or answer whether payment was a year or more before filing. This one-year screen is separate from the legal filing deadline. The litigant decides whether to include the defense.

The LLM classifies answers and answers questions using the active defense's approved text and recorded facts. The host validates every advancing branch. All 21 defenses follow the October 25 scripts. Each begins with its general explanation and follows the applicable fact questions and guidance. A “Finish this defense” instruction advances directly without offering a checkbox.

Offered checkboxes receive an explicit Yes/No choice. Indented boxes mentioned together in the script, such as the first and third SOL boxes, share one question and one answer for both. Facts never select boxes automatically. Each selection section ends with a checklist and a readiness confirmation. An uncertain choice stays local until the user chooses. Unresolved factual questions block advancement until answered; referrals require explicit confirmation that clinic staff addressed the issue. The final review recaps individual checkbox choices and any open clinic issues.

The October 11 preliminary explanations and October 25 defense scripts govern the YAML. Intake additionally verifies `BREACH.DATE`, separately from the last-payment date, so the fourth Breach of Contract checkbox is offered only when both dates are absent. The source scripts and migration decisions are documented in [the October 25 source guide](docs/source-material/2026-10-25/README.md).

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

The former `advocate_bot_qualtrics.decision_tree` compatibility package has been removed; use the canonical modules above. The package-level `process_chat` import remains available. The current source documents are in `docs/source-material/2026-10-11/` (preliminary intake) and `docs/source-material/2026-10-25/` (affirmative defenses).

See [decision-tree structure and field reuse](docs/decision-tree.md) for editing guidance. Restart the demo after changing YAML or Python, then refresh the browser to start a new session.

## Tests

```bash
.venv/bin/python -m pytest
```
