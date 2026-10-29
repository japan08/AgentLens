# AgentLens — evaluate AI agents on what actually matters

> Most agent demos fail silently: the answer *sounds* right while the task
> quietly fails. AgentLens scores an agent on **task success** — the right
> intent, the right tools with the right arguments in the right order, no
> forbidden actions, correct escalation, within latency and cost budgets.

A small, dependency-free Python harness (standard library only) that turns
agent evaluation into a repeatable, CI-gateable check — the same discipline
as unit tests, for systems that talk *and* act.

## Why I built this

While building production AI agents, I found that changing one line of a
system prompt could make demos look better while real task success quietly
dropped. This tool exists so that never ships unnoticed again: every prompt,
model or tool change re-runs the full suite, and scores are tracked version
to version like code.

## Quick start

```bash
# 1. Try the demo (sample support-agent dataset + recorded traces)
python -m agentlens demo

# 2. Evaluate your own recorded traces
python -m agentlens run --cases examples/cases.jsonl \
                        --traces examples/traces.sample.jsonl \
                        --out reports/run1

# 3. Or evaluate a live agent over HTTP
python -m agentlens run --cases examples/cases.jsonl \
                        --endpoint http://localhost:9000/eval \
                        --out reports/run2 --min-success 90   # CI gate

# 4. Diff two runs to catch regressions
python -m agentlens compare reports/run1/report.json reports/run2/report.json \
                        --fail-on-any-new-failure
```

Every run writes `report.json`, `report.md` and a self-contained
`report.html` you can open in a browser or attach to a pull request.

## Dashboard (frontend)

`frontend/index.html` is a zero-build web dashboard for exploring reports:
metric cards, success-by-tag bars, a failure breakdown, and a filterable
case table that shows exactly which checks failed and why. It ships with
the demo report embedded — and you can drag-and-drop (or load) **any**
AgentLens `report.json` to inspect your own runs. No server, no build
step: open the file, or serve the folder with GitHub Pages (a copy lives
in `docs/` for that).

## What gets checked

| Check | What it catches |
|---|---|
| **Task success** | The case passes only if *every* applicable check passes |
| **Intent / routing** | Message routed to the wrong capability or flow |
| **Tool sequence** | Wrong tool, missing step, or steps in the wrong order |
| **Tool arguments** | Right tool called with the wrong ID / value (subset matching) |
| **Forbidden actions** | Blocked intents or tools that must never fire for a case |
| **Answer content** | Required facts missing from the final reply |
| **Escalation** | Agent bluffs instead of handing over — or escalates needlessly |
| **Latency budget** | Per-case `max_latency_ms` (avg + p95 reported) |
| **Cost** | Per-case budget, totals, and **cost per successful task** |
| **Tool budget / loops** | Runaway tool usage and repeated identical calls (agent loops) |
| **LLM-as-judge** | Open-ended answers scored against free-text criteria |
| **Multi-turn** | Whole conversations: per-turn intent + full trajectory |

Metrics are also broken down **per tag**, so you can see that billing cases
pass at 95% while handover cases sit at 60%.

## Dataset format

One JSON object per line. Full agent-task format:

```json
{"id": "refund-1", "input": "I want a refund for order A1042",
 "expected_intent": "refund_request",
 "expected_tools": [{"name": "lookup_order", "args_contains": {"id": "A1042"}},
                    {"name": "create_refund", "args_contains": {"order_id": "A1042"}}],
 "forbidden_tools": ["issue_payment"],
 "expected_answer_contains": ["refund"],
 "should_escalate": false, "max_latency_ms": 3000, "max_cost_usd": 0.02,
 "tags": ["billing"]}
```

Simple intent-classifier datasets are supported too — `utterance`,
`expected`, `expect_flow`, and `expect_not` (negative assertions, e.g.
actions that must never leak into a tenant where they don't belong):

```json
{"utterance": "track my order", "expected": "any", "expect_not": ["place_order", "track_order"]}
```

## Trace format

Record what your agent actually did, one JSON object per line — or expose a
single HTTP endpoint that accepts `{"id", "input"}` and returns this shape:

```json
{"id": "refund-1", "intent": "refund_request",
 "tools": [{"name": "lookup_order", "args": {"id": "A1042"}}],
 "answer": "Refund started for order A1042.",
 "latency_ms": 1980, "cost_usd": 0.0026, "escalated": false}
```

Traces are matched to cases by `id`, or by exact input text.

## Sample result

The bundled demo intentionally contains a realistic failure mix:

- an agent that skips verification and calls a **forbidden refund tool**,
- an agent that **refuses to escalate** to a human,
- an agent that looks up the **wrong order ID** (right tool, wrong argument).

It also covers a **multi-turn** refund conversation, a **subsequence** tool
match (extra housekeeping calls allowed), and an **LLM-as-judge** case.

Sample output: **78.6% task success (11 of 14 cases)** — with the report
naming exactly which cases failed and why. That is the point: failures you
can see are failures you can fix.

## Tests

```bash
python -m unittest discover -s tests -v
```

Covers dataset normalisation, every scoring check, regression comparison,
and the live HTTP runner against a local test server.

## Advanced features (v0.2)

- **Multi-turn cases** — per-turn intents and the full tool trajectory are
  scored; escalation counts if it happens on any turn.
- **Tool-matching modes** — `exact` sequence, or `subsequence` when extra
  housekeeping calls are fine; plus a **tool-call budget** and a **loop
  guard** (same call 3+ times in a row = agent loop).
- **LLM-as-judge** — cases can carry a `judge` block with free-text criteria
  and a minimum score. Use a recorded `judge_score`, the built-in offline
  heuristic judge, or any OpenAI-compatible endpoint as the judge
  (`--judge openai --judge-endpoint ... --judge-model ...`). Spot-check
  judged cases by hand — judge scores drift.
- **`validate` command** — catches duplicate case ids, typos in field
  names, empty inputs and unmatched traces *before* they look like agent
  failures.
- **`trend` command** — tabulates metrics across many run reports so score
  movement version to version is visible at a glance.
- **Failure breakdown** — every report groups failures by check type, so
  you fix the biggest failure class first.

## Roadmap

- Pluggable runners for popular agent frameworks
- Baseline trending wired into git history / CI artifacts
- Flakiness detection across repeated runs of the same dataset

## License

MIT — see [LICENSE](LICENSE).
