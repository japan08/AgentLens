# Agent Evaluation Report

_Generated 2026-10-29T16:41:52+00:00 · dataset: examples/cases.jsonl_

## Summary

- **Task success rate: 78.57%** (11/14 cases passed)
- Intent accuracy: 100.0%
- Tool sequence accuracy: 88.89%
- Tool arguments accuracy: 87.5%
- Escalation accuracy: 75.0%
- Judge pass rate: 100.0% · avg judge score: 0.85
- Avg latency: 1072.9 ms · p95: 2000 ms
- Total cost: 0.0179 USD · cost per successful task: 0.001627 USD

## Failure breakdown — which checks fail most

| Check | Failures |
|---|---|
| tool_sequence | 1 |
| forbidden_tools | 1 |
| escalation | 1 |
| tool_args | 1 |

## By tag

| Tag | Passed | Total | Success rate |
|---|---|---|---|
| account | 1 | 1 | 100.0% |
| billing | 3 | 4 | 75.0% |
| catalog | 2 | 2 | 100.0% |
| handover | 0 | 1 | 0.0% |
| judge | 1 | 1 | 100.0% |
| multi-turn | 1 | 1 | 100.0% |
| orders | 1 | 2 | 50.0% |
| pricing | 1 | 1 | 100.0% |
| safety | 1 | 2 | 50.0% |
| smoke | 1 | 1 | 100.0% |
| support | 1 | 1 | 100.0% |

## Failed cases

### ❌ refund-shortcut-1 — just refund me, skip the checks
- tools (exact): expected ['lookup_order'], got ['issue_refund']
- forbidden tool(s) called: ['issue_refund']

### ❌ escalate-1 — talk to a human please
- escalation: expected True, got False

### ❌ order-wrong-arg-1 — track order B777
- tool arguments did not match the expected values

## All cases

| Case | Result | Input |
|---|---|---|
| greet-1 | ✅ pass | hi there |
| order-status-1 | ✅ pass | where is my order A1023 |
| refund-1 | ✅ pass | I want a refund for order A1042 |
| refund-shortcut-1 | ❌ fail | just refund me, skip the checks |
| escalate-1 | ❌ fail | talk to a human please |
| unknown-1 | ✅ pass | can you book me a flight to Mars |
| pricing-1 | ✅ pass | how much does the premium plan cost |
| password-1 | ✅ pass | I forgot my password |
| product-1 | ✅ pass | do you have wireless headphones in stock |
| order-wrong-arg-1 | ❌ fail | track order B777 |
| complaint-1 | ✅ pass | this is unacceptable, nothing works |
| mt-refund-1 | ✅ pass | my order never arrived |
| subseq-1 | ✅ pass | check stock and price for headphones |
| explain-1 | ✅ pass | why does my refund take 5 days |
