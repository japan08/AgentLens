"""Build the run report and render it as JSON, Markdown and HTML."""
from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from pathlib import Path

from .scoring import aggregate


def build_report(results: list[dict], meta: dict) -> dict:
    from . import __version__
    from .judge import JUDGE_PROMPT_VERSION
    from .safety import structured_findings
    findings: list[dict] = []
    for result in results:
        findings.extend(structured_findings(result["id"], result.get("safety_findings") or []))
        if (result.get("checks") or {}).get("forbidden_tools") is False:
            reason = next((r for r in result.get("reasons") or [] if "forbidden" in r),
                          "a forbidden tool was called")
            findings.append({
                "id": None,
                "case_id": result["id"],
                "severity": "high",
                "category": "Unauthorized tool execution",
                "description": f"The agent executed a tool the case forbids: {reason}.",
                "evidence": f"Recorded tool trajectory for case '{result['id']}': {reason}",
                "component": "agent tool layer",
                "remediation": "Enforce a server-side tool allowlist per intent/case; never rely on the model alone to avoid forbidden tools.",
                "status": "open",
            })
    for i, finding in enumerate(findings, start=1):
        finding["id"] = f"SEC-{i:04d}"
    return {
        "tool": "agentlens",
        "version": __version__,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "meta": {**meta, "judge_prompt_version": JUDGE_PROMPT_VERSION},
        "summary": aggregate(results),
        "security_findings": findings,
        "cases": results,
    }


def _fmt(value, suffix=""):
    return "—" if value is None else f"{value}{suffix}"


def render_markdown(report: dict) -> str:
    s = report["summary"]
    lines = [
        "# Agent Evaluation Report",
        "",
        f"_Generated {report['generated_at']} · dataset: {report['meta'].get('dataset', '?')}_",
        "",
        "## Summary",
        "",
        f"- **Task success rate: {s['task_success_rate']}%** ({s['passed']}/{s['total_cases']} cases passed)",
        f"- Intent accuracy: {_fmt(s['intent_accuracy'], '%')}",
        f"- Tool sequence accuracy: {_fmt(s['tool_sequence_accuracy'], '%')}",
        f"- Tool arguments accuracy: {_fmt(s['tool_args_accuracy'], '%')}",
        f"- Escalation accuracy: {_fmt(s['escalation_accuracy'], '%')}",
        f"- Judge pass rate: {_fmt(s.get('judge_pass_rate'), '%')} · avg judge score: {_fmt(s.get('avg_judge_score'))}",
        f"- Avg latency: {_fmt(s['avg_latency_ms'], ' ms')} · p95: {_fmt(s['p95_latency_ms'], ' ms')}",
        f"- Total cost: {_fmt(s['total_cost_usd'], ' USD')} · cost per successful task: {_fmt(s['cost_per_success_usd'], ' USD')}",
        f"- Avg tool calls per case: {_fmt(s.get('avg_tool_calls'))} · redundant calls: {_fmt(s.get('total_redundant_calls'))}",
        f"- Safety violations: {_fmt(s.get('safety_violations'))} · judge disagreements: {_fmt(s.get('judge_disagreements'))}",
        f"- RAG (avg): faithfulness {_fmt(s.get('avg_rag_faithfulness'))} · relevancy {_fmt(s.get('avg_rag_relevancy'))} · context recall {_fmt(s.get('avg_rag_context_recall'))} · context precision {_fmt(s.get('avg_rag_context_precision'))}",
        "",
    ]
    if s.get("failure_breakdown"):
        lines += ["## Failure breakdown — which checks fail most", "",
                  "| Check | Failures |", "|---|---|"]
        for check, count in s["failure_breakdown"].items():
            lines.append(f"| {check} | {count} |")
        lines.append("")
    if s["by_tag"]:
        lines += ["## By tag", "", "| Tag | Passed | Total | Success rate |", "|---|---|---|---|"]
        for tag, b in sorted(s["by_tag"].items()):
            lines.append(f"| {tag} | {b['passed']} | {b['total']} | {b['success_rate']}% |")
        lines.append("")
    failed = [c for c in report["cases"] if not c["passed"]]
    lines += ["## Failed cases", ""]
    if not failed:
        lines.append("None — all cases passed. 🎉")
    for c in failed:
        lines.append(f"### ❌ {c['id']} — {c['input']}")
        for reason in c["reasons"]:
            lines.append(f"- {reason}")
        for d in c.get("diagnosis") or []:
            lines.append(f"  - 🔎 **{d['check']}** — expected: {d['expected']} · observed: {d['observed']}"
                         + (f" · hint: {d['hint']}" if d.get("hint") else ""))
        lines.append("")
    lines += ["## All cases", "", "| Case | Result | Input |", "|---|---|---|"]
    for c in report["cases"]:
        lines.append(f"| {c['id']} | {'✅ pass' if c['passed'] else '❌ fail'} | {c['input']} |")
    lines.append("")
    return "\n".join(lines)


def render_html(report: dict) -> str:
    s = report["summary"]
    rows = []
    for c in report["cases"]:
        status = '<span style="color:#137333">✅ pass</span>' if c["passed"] else '<span style="color:#b3261e">❌ fail</span>'
        reasons = "<br>".join(html.escape(r) for r in c["reasons"])
        rows.append(
            f"<tr><td>{html.escape(c['id'])}</td><td>{status}</td>"
            f"<td>{html.escape(c['input'])}</td><td>{reasons}</td></tr>"
        )
    tag_rows = "".join(
        f"<tr><td>{html.escape(t)}</td><td>{b['passed']}/{b['total']}</td>"
        f"<td><div style='background:#e6f4ea;height:12px;width:{b['success_rate']}%;min-width:2px'></div>{b['success_rate']}%</td></tr>"
        for t, b in sorted(s["by_tag"].items())
    )
    breakdown_rows = "".join(
        f"<tr><td>{html.escape(k)}</td><td>{v}</td></tr>"
        for k, v in (s.get("failure_breakdown") or {}).items()
    )
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>Agent Evaluation Report</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 2rem auto; max-width: 900px; padding: 0 1rem; color: #1f1f1f; }}
table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; }}
th, td {{ border: 1px solid #ddd; padding: 6px 8px; text-align: left; vertical-align: top; font-size: 14px; }}
th {{ background: #f4f6f4; }}
.metric {{ display: inline-block; margin: 0 1.2rem 0.6rem 0; }}
.metric b {{ font-size: 1.3rem; display: block; }}
</style></head><body>
<h1>Agent Evaluation Report</h1>
<p>Generated {html.escape(report['generated_at'])} · dataset: {html.escape(str(report['meta'].get('dataset', '?')))}</p>
<div>
<span class="metric"><b>{s['task_success_rate']}%</b>task success</span>
<span class="metric"><b>{_fmt(s['intent_accuracy'], '%')}</b>intent accuracy</span>
<span class="metric"><b>{_fmt(s['tool_sequence_accuracy'], '%')}</b>tool sequence</span>
<span class="metric"><b>{_fmt(s['tool_args_accuracy'], '%')}</b>tool arguments</span>
<span class="metric"><b>{_fmt(s['avg_latency_ms'], ' ms')}</b>avg latency</span>
<span class="metric"><b>{_fmt(s['cost_per_success_usd'], ' USD')}</b>cost / success</span>
</div>
<h2>By tag</h2>
<table><tr><th>Tag</th><th>Passed</th><th>Success rate</th></tr>{tag_rows}</table>
<h2>Failure breakdown</h2>
<table><tr><th>Check</th><th>Failures</th></tr>{breakdown_rows}</table>
<h2>Cases</h2>
<table><tr><th>Case</th><th>Result</th><th>Input</th><th>Failure reasons</th></tr>{''.join(rows)}</table>
</body></html>
"""


def write_reports(report: dict, out_dir) -> dict:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = {
        "json": out / "report.json",
        "markdown": out / "report.md",
        "html": out / "report.html",
    }
    paths["json"].write_text(json.dumps(report, indent=2), encoding="utf-8")
    paths["markdown"].write_text(render_markdown(report), encoding="utf-8")
    paths["html"].write_text(render_html(report), encoding="utf-8")
    return {k: str(v) for k, v in paths.items()}
