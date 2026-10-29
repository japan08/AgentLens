# Agent Evaluation Report

_Generated 2026-10-29T16:53:11+00:00 · dataset: examples/intent_cases.jsonl_

## Summary

- **Task success rate: 85.71%** (6/7 cases passed)
- Intent accuracy: 100.0%
- Tool sequence accuracy: —
- Tool arguments accuracy: —
- Escalation accuracy: —
- Judge pass rate: — · avg judge score: —
- Avg latency: 233.6 ms · p95: 300 ms
- Total cost: — · cost per successful task: —

## Failure breakdown — which checks fail most

| Check | Failures |
|---|---|
| forbidden_intent | 1 |

## By tag

| Tag | Passed | Total | Success rate |
|---|---|---|---|
| untagged | 6 | 7 | 85.71% |

## Failed cases

### ❌ case-007 — track my order
- forbidden intent returned: track_order

## All cases

| Case | Result | Input |
|---|---|---|
| case-001 | ✅ pass | hi |
| case-002 | ✅ pass | what services do you offer |
| case-003 | ✅ pass | how much does it cost |
| case-004 | ✅ pass | can I see a demo |
| case-005 | ✅ pass | talk to a human |
| case-006 | ✅ pass | I want to place an order |
| case-007 | ❌ fail | track my order |
