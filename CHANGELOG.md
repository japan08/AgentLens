# Changelog

## 0.4.0 — 2026-10-30

Production-polish release, built from a full repository audit
(PROJECT_AUDIT.md). Zero new dependencies; report format backward
compatible (new fields are additive).

- **Dashboard rebuilt as an app**: collapsible sidebar, header with
  breadcrumb + global trace search, design tokens with complete dark
  and light themes, toasts and error banners. Views: Overview, Traces,
  Evaluations, Experiments, Security, Analytics, Settings — every one
  renders real report data with loading/empty/error states.
- **Trace explorer**: search, status filter, sorting, 25-per-page
  pagination, and a detail panel with checks, diagnosis, execution
  timeline and a size-capped raw JSON viewer.
- **Overview KPIs** all computed from the loaded report, with formulas
  stated in the UI. Tokens show "not recorded" — traces do not carry
  token counts, and the KPI refuses to invent them.
- **Structured security findings**: reports now carry a top-level
  `security_findings` list — `SEC-0001…` records with severity,
  category, description, evidence (pattern type only, never the
  sensitive value), component, remediation and status — covering PII
  exposure, system-prompt leakage and forbidden-tool execution.
- **Experiment reproducibility**: `bench` output gains a `meta` block
  (dataset path + SHA-256, evaluator version, timestamp, config list),
  rendered by the dashboard's Experiments view alongside the metrics
  table and per-case matrix.
- **HTTP API hardening**: optional `AGENTLENS_API_TOKEN` bearer auth,
  5 MB request limit, consistent error envelope
  (`{"error": {"code", "message"}}`) with proper 400/401/404/405/413
  statuses.
- **Integrations**: LlamaIndex-style record converter
  (`convert --format llamaindex`), a FastAPI integration example
  (`examples/fastapi_integration.py`), and `monitor --webhook URL`
  alert delivery.
- **Process docs**: PROJECT_AUDIT.md, IMPLEMENTATION_PLAN.md,
  FEATURE_STATUS.md, RELEASE_NOTES_v0.4.md, QA_REPORT.md.
- Tests: 35 unit tests (5 new for findings/bench meta/converters/
  webhook/server hardening). Demo unchanged at 11/14 (78.57%).

## 0.3.0 — 2026-10-30

Implements the product enhancement blueprint (Phases 1–5, scoped to a
dependency-free core):

- **Trajectories**: every case result now includes an ordered execution
  trajectory (inputs, intents, tool calls, escalation, answer, latency,
  cost) rendered in the dashboard's new Trajectories tab.
- **Failure diagnosis**: failed checks produce structured
  expected-vs-observed entries with a remediation hint, shown in
  Markdown reports and the dashboard.
- **Step efficiency**: redundant-call counting, `max_steps` budgets and
  `expect_efficient` cases; `avg_tool_calls` and `total_redundant_calls`
  summary metrics.
- **Repeated-run stability**: `run --repeat N` for live endpoints,
  per-case pass rates and flaky-case detection.
- **RAG evaluation**: deterministic faithfulness, answer relevancy,
  context recall and context precision with per-case thresholds.
- **Security suite**: PII-exposure and system-prompt-leak answer scans
  (`forbid_pii` / `forbid_leak`), a `safety_violations` metric, sample
  security dataset, and a dashboard Security tab.
- **Benchmarking**: `bench` command compares named configurations
  (models/prompts) on one dataset.
- **Synthetic generation**: `generate` command creates candidate edge
  cases stamped `source: synthetic`, `needs_review: true`.
- **Judge quality controls**: judge prompt version recorded in reports;
  `cross_check` flags recorded-vs-live judge disagreements for review.
- **Integrations**: `convert` command for LangChain-style records and
  OpenTelemetry spans; MCP tool names work natively (sample dataset);
  Python SDK (`agentlens.evaluate`); localhost HTTP API (`serve`).
- **Continuous evaluation**: `monitor` command appends run history and
  alerts (exit 2) on threshold breaches or drops vs the previous run.
- **Dashboard**: tabbed UI — Overview, Cases (with diagnosis),
  Trajectories, Compare (load a second report), Security.
- **Docs**: ARCHITECTURE.md, METRICS.md, BENCHMARKS.md, SECURITY.md,
  CONTRIBUTING.md.

## 0.2.0 — 2026-10-29

- Multi-turn conversation evaluation.
- Subsequence tool matching; tool-call budget and loop guard.
- LLM-as-judge (recorded score, offline heuristic, OpenAI-compatible
  endpoint).
- `validate` command; `trend` command across runs; failure-breakdown
  reporting.
- Zero-build web dashboard for report.json files.

## 0.1.0 — 2026-10-29

- First release: task-success scoring (intent, tool sequence and
  arguments, forbidden actions, escalation, latency and cost budgets),
  JSON/Markdown/HTML reports, `--min-success` CI gate, live HTTP runner.
