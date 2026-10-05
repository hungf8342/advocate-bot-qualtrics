# Decision Tree Project Rules

## Scope
- The application is interactive, using `core/process_chat.py` and `core/engine.py`.
- Consumer-debt routing and screening live in `practice_areas/consumer_debt/`.
- Use canonical imports; the `decision_tree/` compatibility package was removed.
- Document extraction, autonomous fact-sheet traversal, and the simulator are absent.

## Data Contract
- Case facts come from user answers and are session-local.
- Preliminary intake stores the complaint filing date as `FILING-DATE` and
  `session.filing_date`; SOL uses this captured date without asking again.
- Defense analysis belongs in practice-area decision logic. If extraction is
  restored, keep `ComplaintFactSheet` fact-only (`schema_version: "1.1"`).

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
- Ensure engine traversal tests cover:
  - valid branch constraints
  - terminal-node completion
  - summary/open-questions output
