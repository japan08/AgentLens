"""Build the run report and render it as JSON, Markdown and HTML.

Enhancement (v0.3): render_html() now produces a fully styled, dark-mode
dashboard matching the quality of frontend/index.html — metric cards,
tag bars, failure breakdown bars, and a filterable case table with per-case
latency/cost columns.  The generated report.html is completely self-contained
(no external dependencies) and can be opened directly in a browser.
"""
from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from pathlib import Path

from .scoring import aggregate


def build_report(results: list[dict], meta: dict) -> dict:
    return {
        "tool": "agentlens",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "meta": meta,
        "summary": aggregate(results),
        "cases": results,
    }


def _fmt(value, suffix=""):
    return "\u2014" if value is None else f"{value}{suffix}"


def render_markdown(report: dict) -> str:
    s = report["summary"]
    lines = [
        "# Agent Evaluation Report",
        "",
        f"_Generated {report['generated_at']} \u00b7 dataset: {report['meta'].get('dataset', '?')}_",
        "",
        "## Summary",
        "",
        f"- **Task success rate: {s['task_success_rate']}%** ({s['passed']}/{s['total_cases']} cases passed)",
        f"- Intent accuracy: {_fmt(s['intent_accuracy'], '%')}",
        f"- Tool sequence accuracy: {_fmt(s['tool_sequence_accuracy'], '%')}",
        f"- Tool arguments accuracy: {_fmt(s['tool_args_accuracy'], '%')}",
        f"- Escalation accuracy: {_fmt(s['escalation_accuracy'], '%')}",
        f"- Judge pass rate: {_fmt(s.get('judge_pass_rate'), '%')} \u00b7 avg judge score: {_fmt(s.get('avg_judge_score'))}",
        f"- Avg latency: {_fmt(s['avg_latency_ms'], ' ms')} \u00b7 p95: {_fmt(s['p95_latency_ms'], ' ms')}",
        f"- Total cost: {_fmt(s['total_cost_usd'], ' USD')} \u00b7 cost per successful task: {_fmt(s['cost_per_success_usd'], ' USD')}",
        "",
    ]
    if s.get("failure_breakdown"):
        lines += ["## Failure breakdown \u2014 which checks fail most", "",
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
        lines.append("None \u2014 all cases passed. \U0001f389")
    for c in failed:
        lines.append(f"### \u274c {c['id']} \u2014 {c['input']}")
        for reason in c["reasons"]:
            lines.append(f"- {reason}")
        lines.append("")
    lines += ["## All cases", "", "| Case | Result | Input |", "|---|---|---|"]
    for c in report["cases"]:
        lines.append(f"| {c['id']} | {'\u2705 pass' if c['passed'] else '\u274c fail'} | {c['input']} |")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# HTML rendering helpers — kept as plain strings (no f-string) so embedded
# JavaScript curly braces never conflict with Python f-string syntax.
# ---------------------------------------------------------------------------

_CSS = (
    "  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');\n"
    "  :root{--bg:#0f1419;--panel:#1a2230;--panel2:#212c3f;--text:#e8eef5;--muted:#93a4b8;"
    "--green:#2ea043;--red:#e5534b;--blue:#3b82f6;--border:#2c3a50}\n"
    "  *{box-sizing:border-box;margin:0;padding:0}\n"
    "  body{font-family:'Inter',system-ui,sans-serif;background:var(--bg);color:var(--text);min-height:100vh}\n"
    "  header{padding:32px 24px 12px;max-width:1120px;margin:0 auto;border-bottom:1px solid var(--border)}\n"
    "  header h1{font-size:28px;font-weight:700;letter-spacing:-.5px}\n"
    "  header h1 .lens{color:var(--blue)}\n"
    "  header p{color:var(--muted);margin-top:6px;font-size:14px}\n"
    "  main{max-width:1120px;margin:0 auto;padding:20px 24px 60px}\n"
    "  .cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin:20px 0}\n"
    "  .card{background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:16px;transition:border-color .2s}\n"
    "  .card:hover{border-color:var(--blue)}\n"
    "  .card b{font-size:22px;font-weight:700;display:block;margin-bottom:4px}\n"
    "  .card span{color:var(--muted);font-size:12px;font-weight:500;text-transform:uppercase;letter-spacing:.5px}\n"
    "  .card.success b{color:var(--green)}.card.fail b{color:var(--red)}\n"
    "  .grid2{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px}\n"
    "  @media(max-width:760px){.grid2{grid-template-columns:1fr}}\n"
    "  .panel{background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:18px 20px;margin-bottom:12px}\n"
    "  .panel h2{font-size:15px;font-weight:600;margin-bottom:14px}\n"
    "  .bar-row{display:flex;align-items:center;gap:10px;margin:8px 0;font-size:13px}\n"
    "  .bar-row .name{width:120px;color:var(--muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex-shrink:0}\n"
    "  .bar-track{flex:1;background:#0b0f14;border-radius:6px;height:12px;overflow:hidden}\n"
    "  .bar-fill{height:100%;background:var(--green);border-radius:6px;transition:width .6s ease}\n"
    "  .bar-fill.bad{background:var(--red)}\n"
    "  .bar-label{font-size:12px;color:var(--muted);white-space:nowrap;min-width:70px;text-align:right}\n"
    "  .filters{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px;align-items:center}\n"
    "  .filters button{background:var(--panel2);color:var(--muted);border:1px solid var(--border);"
    "border-radius:8px;padding:6px 14px;cursor:pointer;font-size:13px;font-weight:500;transition:all .15s}\n"
    "  .filters button:hover,.filters button.active{border-color:var(--blue);color:#fff;background:#1e3260}\n"
    "  #search{flex:1;min-width:160px;background:var(--panel2);border:1px solid var(--border);"
    "border-radius:8px;color:var(--text);padding:6px 12px;font-size:13px;outline:none;transition:border-color .15s}\n"
    "  #search:focus{border-color:var(--blue)}\n"
    "  .table-wrap{overflow-x:auto}\n"
    "  table{width:100%;border-collapse:collapse;font-size:13px}\n"
    "  th,td{text-align:left;padding:9px 10px;border-bottom:1px solid var(--border);vertical-align:top}\n"
    "  th{color:var(--muted);font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.4px;white-space:nowrap}\n"
    "  tr:last-child td{border-bottom:none}tr:hover td{background:#1e2b3a}\n"
    "  .pass{color:#3fb950;font-weight:600}.fail{color:var(--red);font-weight:600}\n"
    "  .checks{font-size:11px;color:var(--muted);line-height:1.8}\n"
    "  .checks .ok{color:#3fb950}.checks .no{color:var(--red)}\n"
    "  .reasons{color:var(--muted);font-size:12px;line-height:1.6}\n"
    "  .lat-ok{color:#3fb950}.lat-warn{color:#f0a841}.lat-na{color:var(--muted)}\n"
    "  footer{color:var(--muted);text-align:center;padding:0 20px 30px;font-size:12px}\n"
)

_JS = (
    "const s=REPORT.summary;\n"
    "let filter='all';\n"
    "const $=id=>document.getElementById(id);\n"
    "const esc=t=>(t||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');\n"
    "const fmt=(v,sfx)=>(v===null||v===undefined)?'\u2014':v+(sfx||'');\n"
    "const cardData=[\n"
    "  [fmt(s.task_success_rate,'%'),'task success',s.task_success_rate>=80?'success':'fail'],\n"
    "  [s.passed+'/'+s.total_cases,'cases passed',''],\n"
    "  [fmt(s.intent_accuracy,'%'),'intent accuracy',''],\n"
    "  [fmt(s.tool_sequence_accuracy,'%'),'tool sequence',''],\n"
    "  [fmt(s.tool_args_accuracy,'%'),'tool arguments',''],\n"
    "  [fmt(s.escalation_accuracy,'%'),'escalation accuracy',''],\n"
    "  [fmt(s.avg_latency_ms,' ms'),'avg latency',''],\n"
    "  [fmt(s.p95_latency_ms,' ms'),'p95 latency',''],\n"
    "  [fmt(s.cost_per_success_usd,' USD'),'cost / success',''],\n"
    "];\n"
    "$('cards').innerHTML=cardData.map(([v,l,cls])=>"
    "`<div class=\"card ${cls}\"><b>${v}</b><span>${l}</span></div>`).join('');\n"
    "const tags=Object.entries(s.by_tag||{}).sort((a,b)=>b[1].success_rate-a[1].success_rate);\n"
    "$('tagBars').innerHTML=tags.length?tags.map(([name,b])=>"
    "`<div class=\"bar-row\"><span class=\"name\" title=\"${esc(name)}\">${esc(name)}</span>"
    "<div class=\"bar-track\"><div class=\"bar-fill\" style=\"width:${b.success_rate}%\"></div></div>"
    "<span class=\"bar-label\">${b.passed}/${b.total} &middot; ${b.success_rate}%</span></div>`"
    ").join(''):'<p class=\"reasons\">No tags in this report.</p>';\n"
    "const fails=Object.entries(s.failure_breakdown||{});\n"
    "const maxFail=Math.max(1,...fails.map(([,c])=>c));\n"
    "$('failBars').innerHTML=fails.length?fails.map(([name,c])=>"
    "`<div class=\"bar-row\"><span class=\"name\" title=\"${esc(name)}\">${esc(name)}</span>"
    "<div class=\"bar-track\"><div class=\"bar-fill bad\" style=\"width:${(c/maxFail)*100}%\"></div></div>"
    "<span class=\"bar-label\">${c} failure${c===1?'':'s'}</span></div>`"
    ").join(''):'<p class=\"reasons\">No failures 🎉</p>';\n"
    "function renderCases(){\n"
    "  const q=($('search').value||'').toLowerCase();\n"
    "  const rows=(REPORT.cases||[]).filter(c=>{\n"
    "    if(filter==='passed'&&!c.passed)return false;\n"
    "    if(filter==='failed'&&c.passed)return false;\n"
    "    return !q||c.id.toLowerCase().includes(q)||(c.input||'').toLowerCase().includes(q);\n"
    "  });\n"
    "  $('caseRows').innerHTML=rows.map(c=>{\n"
    "    const chk=Object.entries(c.checks||{}).filter(([,v])=>v!==null&&v!==undefined)\n"
    "      .map(([k,v])=>`<span class=\"${v?'ok':'no'}\">${v?'\u2713':'\u2717'} ${k}</span>`).join(' &middot; ');\n"
    "    const lat=c.latency_ms;\n"
    "    const lc=lat===null?'lat-na':lat>3000?'lat-warn':'lat-ok';\n"
    "    const ls=lat===null?'\u2014':lat+' ms';\n"
    "    const cs=(c.cost_usd===null||c.cost_usd===undefined)?'\u2014':'$'+c.cost_usd.toFixed(4);\n"
    "    return `<tr>"
    "<td><code style=\"font-size:12px\">${esc(c.id)}</code></td>"
    "<td class=\"${c.passed?'pass':'fail'}\">${c.passed?'\u2705 pass':'\u274c fail'}</td>"
    "<td style=\"max-width:220px;word-break:break-word\">${esc(c.input)}</td>"
    "<td class=\"${lc}\">${ls}</td><td class=\"lat-na\">${cs}</td>"
    "<td class=\"checks\">${chk}</td>"
    "<td class=\"reasons\">${(c.reasons||[]).map(esc).join('<br>')}</td>"
    "</tr>`;\n"
    "  }).join('')||'<tr><td colspan=\"7\" class=\"reasons\">No cases match.</td></tr>';\n"
    "}\n"
    "document.querySelectorAll('.filters button').forEach(btn=>{\n"
    "  btn.addEventListener('click',()=>{\n"
    "    document.querySelectorAll('.filters button').forEach(b=>b.classList.remove('active'));\n"
    "    btn.classList.add('active');filter=btn.dataset.filter;renderCases();\n"
    "  });\n"
    "});\n"
    "$('search').addEventListener('input',renderCases);\n"
    "renderCases();\n"
)


def render_html(report: dict) -> str:
    """Render a self-contained dark-mode HTML evaluation dashboard.

    Uses plain string concatenation (not f-strings) so embedded JavaScript
    curly braces never conflict with Python f-string parsing.
    """
    generated_at = html.escape(report.get("generated_at", ""))
    dataset = html.escape(str(report.get("meta", {}).get("dataset", "?")))
    source = html.escape(str(report.get("meta", {}).get("source", "")))
    source_part = (f" &nbsp;&middot;&nbsp; source: {source}") if source else ""
    report_json = json.dumps(report, ensure_ascii=False)

    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>AgentLens Report \u2014 {dataset}</title>\n"
        "<style>\n" + _CSS + "</style>\n"
        "</head>\n"
        "<body>\n"
        "<header>\n"
        "  <h1>Agent<span class=\"lens\">Lens</span> &mdash; Evaluation Report</h1>\n"
        f"  <p>Generated {generated_at} &nbsp;&middot;&nbsp; dataset: {dataset}{source_part}</p>\n"
        "</header>\n"
        "<main>\n"
        '  <section class="cards" id="cards"></section>\n'
        '  <div class="grid2">\n'
        '    <section class="panel"><h2>Success by tag</h2><div id="tagBars"></div></section>\n'
        '    <section class="panel"><h2>Failure breakdown</h2><div id="failBars"></div></section>\n'
        "  </div>\n"
        '  <section class="panel">\n'
        "    <h2>Cases</h2>\n"
        '    <div class="filters">\n'
        '      <button data-filter="all" class="active" type="button">All</button>\n'
        '      <button data-filter="passed" type="button">Passed</button>\n'
        '      <button data-filter="failed" type="button">Failed</button>\n'
        '      <input id="search" type="search" placeholder="Search cases\u2026">\n'
        "    </div>\n"
        '    <div class="table-wrap"><table>\n'
        "      <thead><tr>"
        "<th>Case</th><th>Result</th><th>Input</th>"
        "<th>Latency</th><th>Cost</th><th>Checks</th><th>Why it failed</th>"
        "</tr></thead>\n"
        '      <tbody id="caseRows"></tbody>\n'
        "    </table></div>\n"
        "  </section>\n"
        "</main>\n"
        "<footer>AgentLens &mdash; Evaluate AI agents on task success, not just answer quality</footer>\n"
        "<script>\n"
        "const REPORT=" + report_json + ";\n"
        + _JS +
        "</script>\n"
        "</body>\n"
        "</html>"
    )


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
