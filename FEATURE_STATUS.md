# Feature Status — AgentLens

Status key: **Working** (implemented + tested) · **Partially working** ·
**Broken** · **Missing** · **Needs verification**.
Baseline column = state at the v0.4 audit (2026-10-30, v0.3.0).
The v0.4 column is updated as stages complete; nothing is marked
Working for v0.4 without a test or a browser check behind it.

| Feature | v0.3 baseline | v0.4 |
|---|---|---|
| Core scoring (success, intent, tools, args, forbidden, escalation) | Working | |
| Multi-turn cases, subsequence matching, tool budget, loop guard | Working | |
| LLM-as-judge (recorded / heuristic / OpenAI-compatible) + cross-check | Working | |
| Failure diagnosis (expected vs observed + hint) | Working | |
| Trajectory reconstruction + redundant-call counting | Working | |
| Repeated-run stability (`--repeat`, flaky cases) | Working | |
| RAG heuristic metrics (faithfulness/relevancy/recall/precision) | Working | |
| Security scans (PII, system-prompt leak) in answers | Working | |
| Security findings as structured records (id/severity/remediation) | Missing | Working (report `security_findings`, SEC ids; unit-tested) |
| `bench` model/config comparison | Working | |
| Experiment reproducibility metadata (dataset hash, config) | Missing | Working (bench `meta`; unit-tested) |
| `generate` synthetic cases (stamped needs_review) | Working | |
| `validate` dataset/traces checker | Working | |
| `compare` + `trend` across reports | Working | |
| `monitor` history + threshold/drop alerts (exit codes) | Working | |
| Webhook alert delivery from `monitor` | Missing | Working (`--webhook`; tested incl. failure path) |
| Python SDK (`agentlens.evaluate`) | Working | |
| HTTP API (`serve`: /health, /evaluate) | Working | |
| HTTP API auth token + size limits + error envelope | Missing | Working (unit-tested 401/400/404/405) |
| Converters: LangChain-style records, OpenTelemetry spans | Working | |
| Converter: LlamaIndex-style records | Missing | Working (unit-tested + CLI-verified) |
| FastAPI integration example | Missing | Partially working (example ships; eval path tested, FastAPI runtime not — not a project dependency) |
| Dashboard: overview metrics from a loaded report | Working | |
| Dashboard: app shell (sidebar, header, breadcrumbs, global search) | Missing | Working (browser-verified) |
| Dashboard: light theme + design tokens | Missing | Working (browser-verified, both themes) |
| Dashboard: trace explorer (filter/sort/paginate/detail/raw JSON) | Missing | Working (browser-verified) |
| Dashboard: experiments view | Missing | Working (bench meta + tables; second-report diff) |
| Dashboard: analytics view (percentiles, distributions) | Missing | Working (browser-verified) |
| Dashboard: token KPI | Missing (not recorded in traces) | Working as designed: shows “Not recorded” — traces carry no token counts, and the KPI does not fabricate them |
| Lint / type-check configuration | Missing | Missing (still; compileall + tests + CI are the gates — recorded in audit) |
| Database / platform multi-tenancy | Missing (by design — file-based, single-user) | |
