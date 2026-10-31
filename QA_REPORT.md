# QA Report — AgentLens v0.4.0

Date: 2026-10-30. All checks below were executed for this release;
nothing is carried over from v0.3 claims.

## Automated tests

- Unit suite: **35 tests, all passing** (`python -m unittest discover
  -s tests`). New in v0.4: structured security findings (incl. the
  guarantee that a matched PII value never appears in evidence), bench
  reproducibility metadata, LlamaIndex converter, monitor webhook
  delivery (against a local test server, incl. the failure path), and
  HTTP API hardening (401/400/404/405 paths + error envelope).
- `python -m compileall agentlens`: clean.
- Dataset validation: all 5 example datasets (main 14, intent 7,
  RAG 2, security 3, MCP 2 cases) — `validate` OK, traces matched.
- Regression check: demo still **11/14 = 78.57%** — no scoring
  formula changed in v0.4.
- Backward compatibility: the dashboard derives (and labels as
  derived) security findings for pre-0.4 reports that lack the
  top-level `security_findings` field.

## Browser QA (Playwright, headless Chromium)

Views exercised at 1440×900: Overview (dark + light), Traces with a
trace detail opened (checks, diagnosis, timeline, raw JSON),
Security (findings table), Analytics, Experiments (empty state).
Mobile layout checked at 390×844.

- **Console/page errors: none** on any view, desktop or mobile.
- Dark and light themes both render correctly; theme persists via
  localStorage; sidebar collapse works.
- Numbers on screen match the report exactly (14 traces, 11 passed,
  78.57%, 1 security finding SEC-0001, tokens "Not recorded").
- Screenshots captured for all of the above; the dark Overview shot
  is the new `docs/dashboard.png`.

## Known issues / limitations found by QA

1. **Mobile header search** truncates its placeholder at 390 px
   width. The input still works; cosmetic only.
2. No lint/type-check tooling is configured in the project (noted in
   the audit). Gates today: compileall + unit tests + CI matrix.
3. Trace pagination is client-side over the loaded report (stated in
   the UI). Very large reports (thousands of cases) will load fully
   into the browser — acceptable for a report viewer, not a streaming
   observability backend, and the docs say so.
4. The FastAPI example is verified by import-guard and code review,
   not by an executed server — FastAPI is deliberately not a project
   dependency, so its runtime path is exercised by the user, while
   the AgentLens evaluation path it calls is fully unit-tested.
5. Security coverage is the tested patterns (PII formats, leak
   markers, forbidden tools). Passing them is not a security
   guarantee — stated in the UI and docs.

## Verdict

All release gates pass: existing functionality intact (demo and all
datasets unchanged), new features covered by tests or browser checks,
no critical known issues. Remaining items are documented limitations,
not defects.
