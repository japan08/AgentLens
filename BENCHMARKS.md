# Benchmarks and reproducible sample results

AgentLens ships with small **sample** datasets so every number below can
be reproduced exactly with the commands shown. These are demonstration
fixtures — deliberately including failing cases — **not** production
benchmarks of any real agent. Do not quote them as agent performance.

## How to reproduce

```bash
python -m agentlens demo                                   # main sample dataset
python -m agentlens run --cases examples/rag_cases.jsonl --traces examples/rag_traces.sample.jsonl --out /tmp/rag
python -m agentlens run --cases examples/security_cases.jsonl --traces examples/security_traces.sample.jsonl --out /tmp/sec
python -m agentlens run --cases examples/mcp_cases.jsonl --traces examples/mcp_traces.sample.jsonl --out /tmp/mcp
python -m agentlens run --cases examples/intent_cases.jsonl --traces examples/intent_traces.sample.jsonl --out /tmp/intent
```

## Results (AgentLens 0.3.0, recorded 2026-10-30)

| Dataset | Cases | Passed | Task success | Notes |
| --- | ---: | ---: | ---: | --- |
| `examples/cases.jsonl` (support-agent sample) | 14 | 11 | 78.57% | 3 deliberate failures: a forbidden refund tool call, a missed human escalation, a wrong order id in tool arguments |
| `examples/intent_cases.jsonl` (final-chatbot-style intent format) | 7 | 6 | 85.71% | Intent/routing format (`utterance`/`expected`) |
| `examples/rag_cases.jsonl` | 2 | 1 | 50% | The failing case retrieved the wrong document (context recall 0) and answered unsupported content |
| `examples/security_cases.jsonl` | 3 | 1 | 33.33% | Passing: injection refused cleanly. Failing: a PII leak (email + phone in the answer) and a forbidden `issue_refund` call |
| `examples/mcp_cases.jsonl` | 2 | 2 | 100% | MCP-style tool names evaluated as ordinary tool calls |

## Methodology notes

- Datasets and traces are the files in `examples/`; the evaluator is
  deterministic, so re-running produces identical results.
- Latency and cost figures come from the sample traces themselves and
  exist to exercise the metrics, not to describe any real system.
- For real benchmarking, use `agentlens bench` with one case file and
  one trace file per configuration (model/prompt/agent version), and
  publish the dataset version, sample size and configuration alongside
  any numbers.
