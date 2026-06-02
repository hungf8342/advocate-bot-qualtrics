# Decision Tree Project Rules

## Scope
- This repository uses two decision-tree modes:
  - Interactive: user-driven progression via `process_chat(...)`
  - Autonomous: AI-driven progression from `ComplaintFactSheet` JSON

## Data Contract
- `ComplaintFactSheet` is fact-only (`schema_version: "1.1"`).
- Do not reintroduce defense judgment fields into extraction output.
- Defense analysis belongs in decision-tree logic, not extraction.

## LLM Output Requirements
- Interactive chat responses must remain structured:
  - `user_intent`
  - `assistant_reply`
  - `next_node_id`
- `next_node_id` must match one of the current node's branch IDs when advancing.
- If intent is not an answer to the node question, `next_node_id` must be `null`.

## Repository Safety
- Never commit `.env`.
- Never commit generated files in `output/`.
- Keep `.env.example` secret-free.

## Testing
- Add/update tests whenever node schemas, routing validation, or prompts change.
- Ensure autonomous traversal tests cover:
  - valid branch constraints
  - terminal-node completion
  - summary/open-questions output
