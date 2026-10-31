# Implementation Plan — AgentLens v0.4

Derived from PROJECT_AUDIT.md (2026-10-30). Guiding constraints, in the
brief's priority order: preserve working functionality; zero new
runtime dependencies (project invariant); report format stays backward
compatible; no push/deploy without the owner's explicit authorization.

## Stage 1 — Audit (Phase 0)
Done: repo inspected, tests re-run (30 OK), demo re-run (78.57%),
PROJECT_AUDIT.md / FEATURE_STATUS.md / this plan written.

## Stage 2 — Design system + app shell (Phases 1–2)
- Rebuild `frontend/index.html` around CSS design tokens with a dark
  theme (default) and a complete light theme (`data-theme` toggle,
  persisted in localStorage).
- App shell: collapsible sidebar (Overview, Traces, Evaluations,
  Experiments, Security, Analytics, Settings), header with breadcrumb,
  global search, report loader; main content area; toast feedback.
- Only real routes: every sidebar item maps to a working view.
  Settings = theme, report source info, about — no fake controls.
- Overview: KPI cards computed from the loaded report only (total/
  passed/failed traces, pass rate, avg + p95 latency, total cost,
  cost/success, open security findings). Tokens: shown only when
  traces record them, otherwise an explicit "not recorded" state.
  Charts: success-by-tag and failure breakdown bars (as v0.3, restyled).
- Every view gets loading/empty/error states; no dead buttons.

## Stage 3 — Trace explorer (Phase 3)
- Traces view over report cases: search, status filter, sort
  (latency/cost/id), pagination (25/page, client-side over the loaded
  report — stated honestly in the UI copy).
- Detail panel: trajectory timeline (expandable steps), checks,
  diagnosis, tool calls with arguments, judge info, raw JSON viewer
  (`<details>` + pretty-printed JSON, size-capped rendering).

## Stage 4 — Evaluation engine (Phase 4)
- Keep all v0.3 checks. Add structured **security findings** to the
  report (see Stage 6) and judge metadata already present
  (prompt version in `meta`). No formula changes → demo numbers must
  stay 11/14.

## Stage 5 — Experiments (Phase 5)
- `bench` gains a `meta` block: dataset path + SHA-256 of the dataset
  file, evaluator version, judge mode, timestamp — enough to reproduce.
- Dashboard Experiments view: load a bench JSON (or reuse Compare's
  second report) and render the side-by-side table from real data.

## Stage 6 — Security (Phase 6)
- `safety.py` findings become structured records:
  `{id, severity, category, description, evidence, component,
  remediation, status, case_id}` — evidence records the matched
  pattern type and a redacted snippet (never the full secret value).
- Report gains `security_findings` (top-level list) + summary count
  stays compatible. Dashboard Security view renders the records.

## Stage 7 — Analytics + integrations (Phases 7–8)
- Analytics view computed from the loaded report: latency percentiles
  (p50/p95/p99 from per-case values), failure distribution, cost by
  tag, judge agreement; period = the report's own metadata, shown.
- `adapters.py`: LlamaIndex-style record converter + tests.
- `examples/fastapi_integration.py`: minimal working example using the
  SDK (documented as requiring the user's own FastAPI install; the
  conversion path is unit-tested without it).
- `monitor --webhook URL`: POST the alert payload as JSON (stdlib
  urllib), tested against a local test server.

## Stage 8 — Backend hardening (Phase 9)
- `server.py`: optional `AGENTLENS_API_TOKEN` bearer auth, 5 MB body
  limit, consistent error envelope `{"error": {"code", "message"}}`,
  404/405 handling. Localhost default retained and documented.
- No database exists; no schema changes. (See audit: N/A items.)

## Stage 9 — Performance sanity (Phase 10)
- Dashboard: paginated traces, capped raw-JSON rendering, no
  re-render of unchanged views. Engine: no algorithmic changes needed
  at this scale; measured claims avoided.

## Stage 10 — QA + release (Phases 11–12)
- New unit tests for: structured findings, bench metadata, LlamaIndex
  converter, webhook delivery, server auth/limits/envelope.
- Full suite + demo + validate re-run; demo must remain 11/14.
- Browser QA with screenshots: dark + light, desktop + mobile widths,
  every view; check console errors.
- Docs: README refresh, CHANGELOG 0.4.0, RELEASE_NOTES_v0.4.md,
  QA_REPORT.md, FEATURE_STATUS.md final pass.
- Version bump to 0.4.0. **No GitHub push and no Pages deploy without
  the owner's explicit go-ahead** (brief rule 12/13).
