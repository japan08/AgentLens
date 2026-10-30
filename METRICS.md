# AgentLens metrics — definitions and limitations

Every metric below is computed by `agentlens/scoring.py` unless noted.
A case **passes** only when every applicable check passes; checks with
no expectation in the case are skipped (recorded as `null`).

## Headline metrics

| Metric | Definition | Missing-data behaviour |
| --- | --- | --- |
| Task success rate | passed cases ÷ total cases × 100 | 0 cases → 0.0 |
| Intent accuracy | correct intent checks ÷ applicable intent checks | no intent expectations → `null` |
| Tool sequence accuracy | cases whose tool calls match expectations (exact or subsequence mode) ÷ applicable | no tool expectations → `null` |
| Tool arguments accuracy | matched calls whose arguments contain the expected values ÷ applicable | sequence failed → not applicable |
| Escalation accuracy | escalation matched expectation ÷ applicable | no expectations → `null` |
| Avg / p95 latency | mean and 95th-percentile of trace `latency_ms` | traces without latency are excluded |
| Total cost / cost per success | sum of trace `cost_usd`; total ÷ passed cases | no cost data → `null`; costs are as reported by the trace, **not** verified provider billing |
| Avg tool calls | mean number of tool calls per case | — |
| Redundant calls | identical calls (same tool + same arguments) beyond the first occurrence, summed | — |
| Safety violations | count of failed `pii`, `leak` and `forbidden_tools` checks | checks only run when a case opts in |
| Judge pass rate / avg score | judge checks passed ÷ applicable; mean judge score | judge scores are **not** ground truth (see below) |
| Judge disagreements | cases where a recorded judge score and a cross-check judge differ by more than 0.25 | only when `cross_check` is enabled |

## Step efficiency

- `max_steps` caps the number of tool calls for a case.
- `expect_efficient: true` additionally fails a case with any redundant
  repeated call. Loops (same call 3+ times consecutively) are always
  checked separately by the `tool_loop` check.

## RAG metrics (heuristic — read the caution)

Computed in `agentlens/rag.py` from word overlap. They are transparent
proxies for triage, **not** semantic judgments:

- **Faithfulness**: share of the answer's content words that appear in
  the retrieved context. A low score flags possibly unsupported claims;
  a high score does not prove the answer is correct.
- **Answer relevancy**: share of the question's content words that
  appear in the answer.
- **Context recall**: expected context ids retrieved ÷ expected ids.
- **Context precision**: retrieved ids that were expected ÷ retrieved.

Thresholds are set per case in the `rag` block
(`min_faithfulness`, `min_relevancy`, `min_context_recall`,
`min_context_precision`). A metric that cannot be computed (for example
no context in the trace) fails its check when a minimum is set.

## Safety scans

Deterministic pattern scans (regex) over the answer text, enabled per
case with `forbid_pii` / `forbid_leak`. Findings record the *type* of
pattern (email, phone, card number, API key, system-prompt marker),
never the matched value. Pattern scans can miss obfuscated data and can
false-positive on lookalike text — treat them as a tripwire, not proof.

## Stability (repeated runs)

`run --repeat N` against a live endpoint scores each run separately and
reports, per case, the pass rate across runs. A case with
0 < pass rate < 1 is **flaky**. Recorded traces are deterministic, so
stability is only meaningful for live runs.

## LLM-as-judge caution

Judge scores depend on the judge model, prompt and rubric. AgentLens
records the judge prompt version in every report, supports recorded
scores, an offline heuristic judge (content-word coverage of the
criteria — deliberately simple), and any OpenAI-compatible endpoint.
Use `cross_check: true` on a case to flag large disagreements for human
review. Never present judge scores as objective truth.
