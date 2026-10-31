# AgentLens v0.4.0 — Release Notes

Released 2026-10-30. Built from a full audit of the v0.3 codebase
(see PROJECT_AUDIT.md and IMPLEMENTATION_PLAN.md). The release keeps
every v0.3 capability, changes no scoring formula, and adds no
dependencies.

## Highlights

- **A real app shell for the dashboard.** Collapsible sidebar, header
  with breadcrumb and global trace search, design tokens, and complete
  dark + light themes. Seven views — Overview, Traces, Evaluations,
  Experiments, Security, Analytics, Settings — each rendering only
  data from the loaded report, with empty and error states.
- **Trace explorer.** Search, status filter, sorting and pagination
  (25/page, client-side over the loaded report), plus a detail panel
  with checks, structured diagnosis, the execution timeline and a
  size-capped raw JSON viewer.
- **Honest KPIs.** Every Overview number is computed from the loaded
  report and labelled with its formula. Token usage is displayed as
  "not recorded" because AgentLens traces do not carry token counts —
  the dashboard will not fabricate them.
- **Structured security findings.** Reports now include a top-level
  `security_findings` list: stable IDs (`SEC-0001`, …), severity,
  category, description, evidence, component, remediation and status.
  Evidence records the matched pattern type only — sensitive values
  are never written into reports. Coverage: PII exposure, system-
  prompt leakage, forbidden-tool execution.
- **Reproducible experiments.** `agentlens bench` stamps its output
  with the dataset path and SHA-256, the evaluator version and a
  timestamp, so a comparison can be re-run and verified. The
  Experiments view renders the metadata, the metrics table and the
  per-case matrix.
- **Hardened HTTP API.** `serve` supports bearer-token auth via
  `AGENTLENS_API_TOKEN`, rejects bodies over 5 MB with 413, and
  returns a consistent error envelope with proper status codes.
- **Integrations.** LlamaIndex-style record conversion
  (`convert --format llamaindex`), a minimal FastAPI integration
  example, and webhook delivery for monitor alerts
  (`monitor --webhook URL`).

## Compatibility

- Report JSON: additive only. v0.2/v0.3 reports still load in the
  dashboard (security findings are derived and labelled as such) and
  in `compare`/`trend`.
- CLI: one new flag (`monitor --webhook`), one new convert format.
  Nothing removed or renamed.
- Demo result unchanged: 11/14 cases (78.57%).

## Known limitations (also in QA_REPORT.md)

- No database and no platform multi-tenancy — by design; storage is
  files, the API server is a localhost development tool.
- The dashboard is a report viewer: it does not run evaluations or
  collect live traces.
- RAG metrics and the offline judge remain transparent heuristics,
  documented in METRICS.md; LLM judge scores are not ground truth.
- No lint/type-check tooling is configured yet (compileall + the
  35-test suite + CI are the current gates).

## Not done in this release

- Hosted/multi-user deployment, accounts, and a production database
  backend — out of scope for the project's dependency-free core.
- This release was prepared locally; publishing to GitHub happens
  only with the project owner's explicit go-ahead.
