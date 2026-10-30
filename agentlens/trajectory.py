"""Build an ordered, human-readable trajectory for a case + trace.

The trajectory is the execution timeline a developer inspects when a
case fails: the user input, the predicted intent per turn, every tool
call with a safe preview of its arguments, escalation and the final
answer. Each step carries a status derived from the case's checks so a
failure points at the step where it happened.
"""
from __future__ import annotations

import json

_PREVIEW_LIMIT = 120


def _preview(value) -> str:
    text = value if isinstance(value, str) else json.dumps(value, default=str, sort_keys=True)
    return text if len(text) <= _PREVIEW_LIMIT else text[: _PREVIEW_LIMIT - 1] + "…"


def build_trajectory(case: dict, trace: dict, checks: dict) -> list[dict]:
    steps: list[dict] = []

    def add(kind, label, detail="", status="info"):
        steps.append({
            "n": len(steps) + 1,
            "kind": kind,
            "label": label,
            "detail": detail,
            "status": status,
        })

    turns = trace.get("turns") or []
    if turns:
        for idx, turn in enumerate(turns):
            add("input", f"turn {idx + 1} input", _preview(turn["input"]))
            if turn.get("intent") is not None:
                status = "fail" if checks.get("intent") is False else "ok"
                add("intent", f"intent: {turn['intent']}", status=status)
            for tool in turn["tools"]:
                add("tool", f"tool: {tool['name']}", _preview(tool["args"]),
                    "fail" if checks.get("forbidden_tools") is False and tool["name"] in case["forbidden_tools"] else "info")
            if turn.get("escalated"):
                add("escalation", "escalated to human",
                    status="fail" if checks.get("escalation") is False else "ok")
            if turn.get("answer"):
                add("answer", "turn answer", _preview(turn["answer"]))
    else:
        add("input", "user input", _preview(case["input"]))
        if trace.get("intent") is not None:
            add("intent", f"intent: {trace['intent']}",
                status="fail" if checks.get("intent") is False else "ok")
        for tool in trace["tools"]:
            status = "info"
            if checks.get("forbidden_tools") is False and tool["name"] in case["forbidden_tools"]:
                status = "fail"
            add("tool", f"tool: {tool['name']}", _preview(tool["args"]), status)
        if trace.get("escalated"):
            add("escalation", "escalated to human",
                status="fail" if checks.get("escalation") is False else "ok")
        add("answer", "final answer", _preview(trace.get("answer") or ""),
            "fail" if checks.get("answer") is False else "info")

    if checks.get("tool_loop") is False:
        add("warning", "tool loop detected", "same call repeated 3+ times in a row", "fail")
    if trace.get("latency_ms") is not None:
        add("meta", f"latency {trace['latency_ms']} ms",
            status="fail" if checks.get("latency") is False else "info")
    if trace.get("cost_usd") is not None:
        add("meta", f"cost ${trace['cost_usd']}",
            status="fail" if checks.get("cost") is False else "info")
    return steps


def count_redundant_calls(tools: list[dict]) -> int:
    """Identical calls (same tool + same args) beyond the first occurrence.

    Consecutive duplicates are a loop problem; scattered duplicates are
    wasted work. Both count as redundant for efficiency purposes.
    """
    seen = set()
    redundant = 0
    for tool in tools:
        key = tool["name"] + "|" + json.dumps(tool["args"], sort_keys=True, default=str)
        if key in seen:
            redundant += 1
        seen.add(key)
    return redundant
