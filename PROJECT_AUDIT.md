# Project Audit — AgentLens at v0.3.0

Audited 2026-10-30, before v0.4 work. All results below were re-run for
this audit, not carried over from earlier claims.

## What the project is

- A dependency-free Python (>= 3.10) CLI + library for evaluating AI
  agents from recorded traces, plus a zero-build single-file web
  dashboard (`frontend/index.html`, copied to `docs/` for GitHub Pages).
- Storage is files (JSONL datasets/traces, JSON reports). There is **no
  database, no multi-tenancy, and no user accounts** in the platform
  itself. The HTTP API (`agentlens/server.py`) is a localhost
  development server.
- Local folder is the source of truth; it is not a git working copy
  (GitHub sync is via snapshot pushes; last verified remote commit
  `dea2ad1`).

## Verified state (re-run 2026-10-30)

- Unit tests: **30 run, OK** (`python -m unittest discover -s tests`).
- `python -m compileall agentlens`: clean.
- Demo: 14 cases, task success **78.57%** (3 deliberate failures).
- All 5 example datasets validate (main, intent, RAG, security, MCP).
- CI (`.github/workflows/ci.yml`): runs the test suite on Python
  3.10/3.11/3.12 plus demo/validate smoke steps.
- No lint or type-check tooling is configured (no ruff/mypy/pyright
  config anywhere). "Lint/type check" for this project today means
  compileall + tests only. Recorded as tech debt, not silently skipped.

## Architecture (as found)

- `agentlens/` — 19 modules, ~2,400 lines. Core flow:
  `dataset.py` (case loading/normalisation) → `trace.py` (trace
  normalisation) → `scoring.py` (all checks + diagnosis) →
  `report.py` (JSON/Markdown/HTML reports).
- Supporting: `judge.py` (recorded/heuristic/OpenAI-compatible judge),
  `rag.py` (word-overlap RAG heuristics), `safety.py` (PII/leak regex
  scans), `trajectory.py`, `compare.py`, `bench.py`, `generate.py`,
  `monitor.py`, `adapters.py` (LangChain-style + OpenTelemetry
  converters), `api.py` (SDK), `server.py` (HTTP API), `cli.py`.
- Report JSON shape: `{tool, version, generated_at, meta, summary,
  cases[]}`; each case carries checks, reasons, diagnosis, trajectory,
  tool_calls, latency_ms, cost_usd, judge fields, rag, safety_findings.
- Dashboard v0.3: tabbed single file (Overview/Cases/Trajectories/
  Compare/Security), dark-only, embedded demo report, load any
  report.json via file picker/drag-drop.

## Findings

### Broken
- Nothing in the engine is broken: tests, demo, validate, bench,
  generate, convert, monitor, SDK and HTTP API all ran in the v0.3
  verification pass and again in this audit (tests + demo).

### Partially working / shallow
- **Security findings have no structure**: per-case `safety_findings`
  are `{check, detail}` only — no finding ID, severity, category,
  evidence discipline, remediation or status (Phase 6/7 gap).
- **Experiments lack reproducibility metadata**: `bench` output has no
  dataset hash, evaluator version or config record (Phase 5 gap).
- **Dashboard is a report viewer, not an app**: no sidebar/app shell,
  no light theme, no trace explorer (search/filter/pagination/detail/
  raw JSON), no analytics view, no experiments view, no global search.
- **HTTP API hardening**: no authentication option, no request-size
  limit, errors are bare strings, no consistent error envelope.
- **Token usage is not captured anywhere**: traces carry latency and
  cost but no token counts, so any "total tokens" KPI would be
  fabricated. v0.4 must show tokens as *not recorded* unless a trace
  provides them.
- **Integrations**: converters exist for LangChain-style records and
  OpenTelemetry spans; no LlamaIndex converter, no FastAPI example, no
  webhooks (monitor alerts are stdout/exit-code only).

### Missing (per the v0.4 brief, honestly scoped)
- Design system (tokens, light theme, app shell) — Phase 1/2.
- Trace explorer — Phase 3.
- Analytics module — Phase 7 (computable from report data only).
- Webhook alerting — Phase 8.
- API token auth + limits — Phase 9.

### Explicitly out of scope / not applicable
- **Database work (Phase 9)**: there is no database. Adding one would
  violate "avoid unnecessary dependencies / don't rewrite". File-based
  storage stays; the applicable Phase 9 items (validation, error
  envelope, auth, limits) are applied to the HTTP API instead.
- **Platform multi-tenancy**: does not exist, so there is nothing to
  isolate. The *security suite* tests whether evaluated agents leak
  across tenants in their traces — a different thing, already present.
- **Hosted production deployment**: the dashboard is a static report
  viewer; the API server is documented as localhost development use.

### Risks
- Single-file dashboard is growing; keep it structured (tokens +
  small render functions) rather than splitting into a build pipeline
  the project deliberately does not have.
- Report-format changes must stay backward compatible: the dashboard
  and `compare` consume older reports (v0.2/v0.3) too.
