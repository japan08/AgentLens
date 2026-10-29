"""Compare two run reports to catch regressions between versions.

The point of tracking scores version to version: a prompt or model change
that quietly drops task success should fail loudly, here — not in front
of a user.
"""
from __future__ import annotations

import json
from pathlib import Path

METRICS = [
    "task_success_rate",
    "intent_accuracy",
    "tool_sequence_accuracy",
    "tool_args_accuracy",
    "escalation_accuracy",
    "avg_latency_ms",
    "cost_per_success_usd",
]


def load_report(path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def compare_reports(old: dict, new: dict) -> dict:
    old_cases = {c["id"]: c for c in old.get("cases", [])}
    new_cases = {c["id"]: c for c in new.get("cases", [])}

    newly_failing = sorted(
        cid for cid in old_cases.keys() & new_cases.keys()
        if old_cases[cid]["passed"] and not new_cases[cid]["passed"]
    )
    newly_passing = sorted(
        cid for cid in old_cases.keys() & new_cases.keys()
        if not old_cases[cid]["passed"] and new_cases[cid]["passed"]
    )

    # Per-case check diffs: which specific check newly failed or newly passed?
    check_diffs: dict[str, dict] = {}
    for cid in old_cases.keys() & new_cases.keys():
        old_checks = old_cases[cid].get("checks", {})
        new_checks = new_cases[cid].get("checks", {})
        newly_failed_checks = [
            k for k in old_checks
            if old_checks.get(k) is not False and new_checks.get(k) is False
        ]
        newly_fixed_checks = [
            k for k in new_checks
            if old_checks.get(k) is False and new_checks.get(k) is not False
        ]
        if newly_failed_checks or newly_fixed_checks:
            check_diffs[cid] = {
                "newly_failed": newly_failed_checks,
                "newly_fixed": newly_fixed_checks,
            }

    metric_deltas = {}
    for m in METRICS:
        o, n = old["summary"].get(m), new["summary"].get(m)
        if o is not None and n is not None:
            metric_deltas[m] = {"old": o, "new": n, "delta": round(n - o, 4)}

    return {
        "metric_deltas": metric_deltas,
        "success_rate_delta": metric_deltas.get("task_success_rate", {}).get("delta"),
        "newly_failing": newly_failing,
        "newly_passing": newly_passing,
        "check_diffs": check_diffs,
        "added_cases": sorted(new_cases.keys() - old_cases.keys()),
        "removed_cases": sorted(old_cases.keys() - new_cases.keys()),
    }


def build_trend(reports: list[dict]) -> list[dict]:
    """One row per report, oldest first, for tracking scores over time."""
    ordered = sorted(reports, key=lambda r: r.get("generated_at", ""))
    rows = []
    for r in ordered:
        s = r["summary"]
        rows.append({
            "generated_at": r.get("generated_at", "?"),
            "dataset": r.get("meta", {}).get("dataset", "?"),
            "task_success_rate": s.get("task_success_rate"),
            "intent_accuracy": s.get("intent_accuracy"),
            "tool_sequence_accuracy": s.get("tool_sequence_accuracy"),
            "tool_args_accuracy": s.get("tool_args_accuracy"),
            "avg_latency_ms": s.get("avg_latency_ms"),
            "cost_per_success_usd": s.get("cost_per_success_usd"),
        })
    return rows


def render_trend(rows: list[dict]) -> str:
    lines = [
        "# Evaluation trend",
        "",
        "| When | Dataset | Task success | Intent | Tool seq | Tool args | Avg latency | Cost / success |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        def f(v, suffix=""):
            return "—" if v is None else f"{v}{suffix}"
        lines.append(
            f"| {r['generated_at']} | {r['dataset']} | {f(r['task_success_rate'], '%')} "
            f"| {f(r['intent_accuracy'], '%')} | {f(r['tool_sequence_accuracy'], '%')} "
            f"| {f(r['tool_args_accuracy'], '%')} | {f(r['avg_latency_ms'], ' ms')} "
            f"| {f(r['cost_per_success_usd'], ' USD')} |"
        )
    lines.append("")
    if len(rows) >= 2:
        first, last = rows[0], rows[-1]
        if first["task_success_rate"] is not None and last["task_success_rate"] is not None:
            delta = round(last["task_success_rate"] - first["task_success_rate"], 2)
            arrow = "🟢" if delta >= 0 else "🔴"
            lines.append(f"{arrow} Task success moved {delta:+}% from first to latest run.")
            lines.append("")
    return "\n".join(lines)


def render_comparison(comp: dict) -> str:
    lines = ["# Report comparison", ""]
    if comp["success_rate_delta"] is not None:
        arrow = "🔴" if comp["success_rate_delta"] < 0 else "🟢"
        lines.append(f"{arrow} Task success rate changed by {comp['success_rate_delta']:+}%")
        lines.append("")
    lines.append("| Metric | Old | New | Delta |")
    lines.append("|---|---|---|---|")
    for m, d in comp["metric_deltas"].items():
        lines.append(f"| {m} | {d['old']} | {d['new']} | {d['delta']:+} |")
    lines.append("")
    if comp["newly_failing"]:
        lines.append(f"**Newly failing (regressions):** {', '.join(comp['newly_failing'])}")
    if comp["newly_passing"]:
        lines.append(f"**Newly passing (fixes):** {', '.join(comp['newly_passing'])}")
    if not comp["newly_failing"] and not comp["newly_passing"]:
        lines.append("No case changed pass/fail status.")
    lines.append("")
    # Per-case check diffs (new in v0.3)
    check_diffs = comp.get("check_diffs", {})
    if check_diffs:
        lines.append("## Check-level changes")
        lines.append("")
        lines.append("| Case | Newly failing checks | Newly fixed checks |")
        lines.append("|---|---|---|")
        for cid, diff in sorted(check_diffs.items()):
            failed = ", ".join(diff["newly_failed"]) or "—"
            fixed = ", ".join(diff["newly_fixed"]) or "—"
            lines.append(f"| {cid} | {failed} | {fixed} |")
        lines.append("")
    return "\n".join(lines)
