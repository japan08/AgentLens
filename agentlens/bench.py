"""Benchmark several agent configurations on the same dataset.

Each configuration is a named set of traces for the same cases (for
example two models, or two prompt versions). The benchmark scores every
configuration with the normal engine and lays the headline metrics side
by side, so model/prompt choices are made on task success, cost and
safety together — not on vibes.
"""
from __future__ import annotations

from .report import build_report
from .scoring import score_case
from .trace import find_trace, index_traces

_COLUMNS = [
    ("task_success_rate", "Success %"),
    ("passed", "Passed"),
    ("avg_latency_ms", "Avg latency ms"),
    ("total_cost_usd", "Total cost $"),
    ("cost_per_success_usd", "Cost/success $"),
    ("avg_tool_calls", "Avg tool calls"),
    ("safety_violations", "Safety violations"),
]


def run_benchmark(cases: list[dict], configs: dict[str, list[dict]], meta: dict | None = None) -> dict:
    results = {}
    per_case: dict[str, dict[str, bool]] = {}
    for name, traces in configs.items():
        index = index_traces(traces)
        scored = [score_case(case, find_trace(index, case)) for case in cases]
        report = build_report(scored, {"dataset": "benchmark", "source": name})
        results[name] = report["summary"]
        for row in scored:
            per_case.setdefault(row["id"], {})[name] = row["passed"]
    return {"meta": meta or {}, "configs": results, "per_case": per_case}


def render_benchmark(bench: dict) -> str:
    names = list(bench["configs"])
    lines = ["# AgentLens benchmark", "",
             "| Metric | " + " | ".join(names) + " |",
             "| --- | " + " | ".join("---" for _ in names) + " |"]
    for key, label in _COLUMNS:
        cells = []
        for name in names:
            value = bench["configs"][name].get(key)
            cells.append("—" if value is None else str(value))
        lines.append(f"| {label} | " + " | ".join(cells) + " |")
    lines += ["", "## Per-case results", "",
              "| Case | " + " | ".join(names) + " |",
              "| --- | " + " | ".join("---" for _ in names) + " |"]
    for case_id, row in bench["per_case"].items():
        cells = ["✅" if row.get(n) else "❌" for n in names]
        lines.append(f"| {case_id} | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"
