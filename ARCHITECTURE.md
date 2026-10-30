# AgentLens architecture

AgentLens is a dependency-free Python core with optional surfaces around
it. The core never needs a server, a database or a model provider.

## Data flow

```
cases (JSONL) ──┐
                ├─► dataset.normalize_case ─┐
traces (JSONL) ─┤                           ├─► scoring.score_case ─► report.build_report
live endpoint ──┤   trace.normalize_trace ──┘        │                     │
converters ─────┘                                    │                     ├─► JSON / Markdown / HTML
                                                     │                     └─► dashboard (static viewer)
                                                     ├─ trajectory.build_trajectory (per-case timeline)
                                                     ├─ rag.rag_scores (when a case has a `rag` block)
                                                     └─ safety.scan_answer (when a case forbids PII/leaks)
```

## Modules

| Module | Responsibility |
| --- | --- |
| `dataset.py` | Load and normalize evaluation cases (both trace-style and intent-style datasets). |
| `trace.py` | Load/normalize recorded traces; collect traces live from an HTTP endpoint. |
| `scoring.py` | All deterministic checks, failure diagnosis, aggregation. A case passes only if every applicable check passes. |
| `trajectory.py` | Ordered per-case execution timeline + redundant-call counting. |
| `rag.py` | Deterministic heuristic RAG metrics (faithfulness/relevancy/context recall/precision). |
| `safety.py` | Regex-based PII and system-prompt-leak scans over answers. |
| `judge.py` | LLM-as-judge: recorded scores, offline heuristic judge, OpenAI-compatible endpoint judge. Prompt version is recorded in every report (`meta.judge_prompt_version`). |
| `compare.py` | Regression diff between two reports; trend tables across many reports. |
| `bench.py` | Multi-configuration benchmark on one dataset. |
| `generate.py` | Synthetic candidate-case generation (always stamped `needs_review`). |
| `adapters.py` | Format converters: LangChain-style records and OpenTelemetry spans → AgentLens traces. |
| `api.py` | Programmatic entry point (`agentlens.evaluate`). |
| `server.py` | Optional localhost HTTP API (`POST /evaluate`) built on the stdlib. |
| `monitor.py` | Continuous-evaluation bookkeeping: history file + threshold/drop alerts. |
| `validate.py` | Dataset hygiene checks before running. |
| `report.py` | JSON/Markdown/HTML rendering. |

## Design decisions

- **Deterministic first.** Tool trajectories, arguments, forbidden
  actions, budgets and safety scans are exact checks. Probabilistic
  judge scores are kept separate and labelled, never blended into the
  deterministic result.
- **Standard library only** for the core, so the tool runs anywhere
  Python 3.10+ runs and is trivial to gate in CI.
- **Everything is a file.** Datasets, traces and reports are portable
  JSON/JSONL; the dashboard is one static HTML file that renders any
  `report.json`.
- **Failure diagnosis is data, not prose.** Every failed case carries
  structured `diagnosis` entries (check, expected, observed, hint) and a
  `trajectory`, so UIs and CI can point at the exact step that failed.
- **Versioned reports.** Reports record the AgentLens version and the
  judge prompt version; dataset/trace formats evolve by adding optional
  fields, never by renaming existing ones.

## Extension points

- Add a check: extend `CHECK_KEYS` and `score_case` in `scoring.py`,
  add a diagnosis hint, cover it with a unit test.
- Add an input format: write a converter in `adapters.py` that returns
  native trace dicts.
- Add an output: consume the report dict from `report.build_report`.
