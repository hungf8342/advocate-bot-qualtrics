# Interactive tree simulator (training tool)

This package role-plays a **simulated defendant** against the production [`InteractiveChatEngine`](../src/advocate_bot_qualtrics/decision_tree/interactive_host.py). It is for **training and debugging**, not for end-user deployment.

Simulator code lives in `src/advocate_bot_qualtrics/simulator/` and is intentionally **not** exported from the main production package.

## Quick start

```bash
pip install -e .
# Requires ANTHROPIC_API_KEY in .env (two LLM calls per user turn)

python scripts/run_interactive_simulator.py \
  --persona "Pretend you're a defendant who needs lots of terms explained."

python scripts/run_interactive_simulator.py \
  --persona-file simulator/personas/confused_defendant.md
```

## Batch runs

```bash
# One run per persona file
python scripts/run_interactive_simulator.py --persona-dir simulator/personas/

# Each persona × 2 runs
python scripts/run_interactive_simulator.py \
  --persona-dir simulator/personas/ \
  --repeat 2
```

Transcripts are written to `output/simulator_runs/{timestamp}_{persona_slug}_{run_index}.md`.

## Outputs

| Output | Default path | Notes |
|--------|--------------|-------|
| Transcript (markdown) | `output/simulator_runs/…` | Rich per-turn routing debug |
| JSON sidecar | same stem with `.json` | Pass `--json` |
| Excel session fields | `output/simulator_session_fields.xlsx` | Separate from manual demo exports |

Each transcript includes:

- Persona and facts file used
- Per-turn **Routing** line: `intent`, `branch`, `confidence`, `next_node`
- Optional simulator `notes` from the LLM
- Final session summary (node answers, SOL/FDCPA outcomes)

## CLI flags

| Flag | Default | Purpose |
|------|---------|---------|
| `--facts-json` | sample fixture | ComplaintFactSheet JSON |
| `--persona` / `--persona-file` | — | Role-play instructions |
| `--persona-dir` | — | Batch over `.md`/`.txt` files |
| `--repeat` | `1` | Runs per persona |
| `--output` | auto | Single-run transcript path |
| `--output-dir` | `output/simulator_runs/` | Batch output directory |
| `--session-fields-xlsx` | `output/simulator_session_fields.xlsx` | Excel export target |
| `--max-turns` | `50` | Safety cap |
| `--stall-turns` | `5` | Stop if stuck on same node |
| `--qa-turns` | `0` | Post-complete Q&A turns |
| `--json` | off | Write JSON sidecar |

## Persona authoring tips

- Describe **behavior**, not tree branches (e.g. "asks for definitions", "disputes filing date", "hedges with I think").
- Personas can contradict fact-sheet dates to test dispute flows.
- Use `--stall-turns` for personas that ask many clarifying questions on one node.

When a persona combines an **answer with a related term question** (e.g. "Yes, but what does filing date mean?"), the production bot should route `ask_about_complaint`, answer the question, and **re-ask the same tree node** before advancing. General legal-advice follow-ups (e.g. "Can they arrest me?" after denying a threat) should still advance.

## Environment

| Variable | Default | Purpose |
|----------|---------|---------|
| `SIMULATOR_USER_MODEL` | `ANTHROPIC_MODEL` (`claude-sonnet-4-6`) | Simulated defendant LLM |
| `ANTHROPIC_CHAT_MODEL` | Haiku | Production tree router (unchanged) |
| `SESSION_FIELDS_XLSX_PATH` | set per run by CLI | Excel append target |

## Separation from production

The simulator may import only:

- `InteractiveChatEngine` / `InteractiveChatStep`
- `ComplaintFactSheet` loading
- Environment override for Excel path

It does **not** modify production `config.py`, `decision_tree/`, or prompts.
