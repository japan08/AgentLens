"""Programmatic API — evaluate from Python without the CLI.

    from agentlens.api import evaluate

    report = evaluate(cases, traces)   # raw dicts in the JSONL formats
    print(report["summary"]["task_success_rate"])

``cases`` and ``traces`` are lists of raw dicts exactly as they would
appear in the JSONL files; they are normalized the same way the CLI
normalizes them, so SDK and CLI results agree.
"""
from __future__ import annotations

from .dataset import normalize_case
from .report import build_report
from .scoring import score_case
from .trace import find_trace, index_traces, normalize_trace


def evaluate(cases: list[dict], traces: list[dict], judge=None) -> dict:
    norm_cases = [normalize_case(c, i + 1) for i, c in enumerate(cases)]
    norm_traces = [normalize_trace(t) for t in traces]
    index = index_traces(norm_traces)
    results = [score_case(case, find_trace(index, case), judge=judge) for case in norm_cases]
    return build_report(results, {"dataset": "sdk", "source": "agentlens.api.evaluate"})
