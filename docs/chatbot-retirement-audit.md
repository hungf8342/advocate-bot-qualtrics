# Chatbot retirement audit

The guided clickthrough is the application to use and extend. This audit identifies
retirement candidates; it does not delete application code. Paths below are relative
to the repository root. Python module paths without a prefix are relative to
`src/advocate_bot_qualtrics/`.

## Remove with the old chatbot

| Files | Purpose being retired |
| --- | --- |
| `scripts/interactive_chat_demo.py`, `scripts/assets/debt_chat.css` | Gradio conversation interface |
| `core/engine.py`, `core/process_chat.py` | Conversation-driven traversal, answer classification, and transcript handling |
| `core/bundle.py`, `practice_areas/consumer_debt/bundle.py` | Registry and wiring for the conversation engine |
| `core/confidence.py`, `core/dates.py`, `practice_areas/consumer_debt/date_confidence.py` | Conversation answer confidence and free-text date handling |
| `practice_areas/consumer_debt/computations.py` | Old bundle's SOL/FDCPA computation hooks; the clickthrough uses the script logic in `affirmative_defenses.py` |
| `core/export_writer.py`, `practice_areas/consumer_debt/field_export.py` | Legacy Excel session/confidence export; unrelated to clickthrough research collection |
| `prompts/decision_tree_chat_system.md`, `prompts/confidence_scoring_calibration.md` | Old conversation routing and confidence prompts |

These files can be retired together after the import and test changes below.
They are not an independent set of files that can simply be unlinked today.

## Required changes before deletion

1. Remove old chatbot re-exports from `__init__.py` and `core/__init__.py`.
   Importing even a shared core schema currently loads the engine and bundle
   registry. The registry eagerly registers the legacy consumer-debt bundle.
2. Remove or relocate the `scripted_engine` fixture and its imports in
   `tests/conftest.py`; otherwise even guided-only test collection imports the
   retired modules.
3. Retire chatbot-only tests and port useful shared assertions to clickthrough
   tests. In particular, `tests/test_sol_dependency_map.py` mixes map tests with
   traversal through `scripted_engine`: preserve the map tests and replace that
   traversal with clickthrough coverage.
4. Trim legacy prompt/confidence/Excel configuration from `config.py` and update
   `.env.example` to describe only supported behavior. Keep prompt paths and the
   Z.ai configuration used by the clickthrough clarification chat.
5. Remove `gradio` and `openpyxl` dependencies once their retired UI/export code
   and tests are gone. Remove `anthropic` only after removing its import and unused
   `AnthropicClient` from `llm/client.py`, and cleaning up the commented provider
   path/configuration. Keep `openai`: Z.ai calls use its compatible client.
6. Replace legacy setup/architecture instructions in README and current developer
   documentation. Historical source/provenance documents can remain as history.

Chatbot-specific test candidates include:

- `tests/core/test_bundle_registry.py`, `tests/core/test_engine_terminal_qa.py`
- `tests/test_process_chat_schema.py`, `tests/test_process_chat_validation.py`
- `tests/test_confidence_calibration.py`, `tests/test_session_field_export.py`
- `tests/test_demo_case_details.py`

Other older tests cover shared rules, schemas, source text, and session behavior,
sometimes through the chatbot engine. Review/port those assertions rather than
deleting every test without `guided` in its name. Keep
`tests/core/test_tree_definition.py` and the relevant shared-rule tests.

## Keep: clickthrough and shared dependencies

| Files | Why they remain |
| --- | --- |
| `scripts/guided_clickthrough_demo.py`, `scripts/assets/guided_sol/` | FastAPI application and browser UI |
| `practice_areas/consumer_debt/guided_*.py`, `guided_*.yaml` | Replay, edits, pages, debug navigation, formatting, and collection |
| `practice_areas/consumer_debt/interactive_tree.yaml`, `tree.py` | `guided_sol._prototype_tree()` copies this tree and applies guided content patches |
| `practice_areas/consumer_debt/affirmative_defenses.py` | Conditions, actions, facts, date cutoffs, and text personalization |
| `practice_areas/consumer_debt/session.py`, `preliminary.py` | Session state, intake field parsing, and answer application |
| `practice_areas/consumer_debt/sol_dependency_map.py`, `sol_checkbox_dependencies.yaml` | Checkbox dependencies and review after edits |
| `practice_areas/consumer_debt/host_extras.py` | `_script_text` is used by guided pages and formatting; extract it before removing the rest of this file |
| `core/schemas.py`, `core/tree_definition.py`, `core/session.py`, `core/errors.py` | Shared node/response validation, tree loading, answer records, and chat error type |
| `llm/chat_structured.py`, active `OpenAIClient` in `llm/client.py` | Clickthrough `/api/help` still calls the model |
| `prompts/guided_sol_clarification_system.md`, active configuration in `config.py` | Non-advancing clarification chat |
| `scripts/extract_guided_script_formatting.py`, source documents, complaint examples | Source formatting extraction, provenance tests, and example intake |
| `tests/test_guided*.py`, relevant shared-rule/schema/LLM tests | Regression coverage for the application being retained |

Do not delete `output/clickthrough/` or its SQLite database/CSVs as part of code
cleanup. Those are research records, not legacy code. Keep them out of Git.

## Optional second cleanup

After the first retirement, move `_script_text` to a shared rendering module and
remove the remaining chatbot-only rendering/debug/restart helpers in
`host_extras.py`. Review session fields, compatibility constants in `tree.py`, and
schema fields individually for remaining use. Do not rename or prune YAML nodes
just because the clickthrough does not display them: validation, branch targets,
session bindings, collection fingerprints, and historical answer IDs can depend
on them. Consolidating the base tree and guided overlays is a separate migration.

## Verification

Before applying removals, test an isolated copy with the candidate modules and
prompts removed, both package initializers detached from the chatbot, and the old
test fixture removed. Run the guided suite and active structured-chat tests there.
This verifies the proposed boundary without altering the working application.

This experiment passed: **430 tests passed** using
`python -m pytest -q tests/test_guided* tests/test_chat_structured.py` in the
isolated copy. All ten Python module candidates in the removal table, the old
Gradio script/CSS, and both old prompts were absent. The package initializers and
legacy test fixture were detached as described above. The installed dependencies
were retained, so this does not independently verify dependency uninstallation.
The run emitted one FastAPI/Starlette test-client dependency deprecation warning.

For the actual cleanup, also run the entire remaining suite and verify normal
collection, debug collection isolation, final completion, changed-answer
invalidation, and non-advancing clarification. Live provider availability is
separate from mocked clarification API tests.

`guided_collection.py` fingerprints selected source files into the recorded tree
version. Refactoring those files can change the version and browser-review
behavior even if the intended question flow stays the same; preserve historical
collection data and test that transition.
