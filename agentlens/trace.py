"""Load recorded agent runs ("traces") from a JSONL file, or collect them
live from an HTTP agent endpoint.

Trace format (one JSON object per line)::

    {"id": "refund-1",                // or "input": "<the case input>"
     "intent": "refund_request",      // or "predicted"
     "flow": "refund_flow",
     "tools": [{"name": "lookup_order", "args": {"id": "A1"}}],
     "answer": "Your refund is on its way",
     "latency_ms": 1240, "cost_usd": 0.004,
     "escalated": false}

A trace is matched to a case by ``id`` when present, otherwise by the
exact ``input``/``utterance`` text.
"""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path


def _norm_tool(entry):
    if isinstance(entry, str):
        return {"name": entry, "args": {}}
    if isinstance(entry, dict):
        if "function" in entry and isinstance(entry["function"], dict):
            fn = entry["function"]
            args = fn.get("arguments") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {"_raw": args}
            return {"name": fn.get("name", ""), "args": args}
        return {"name": entry.get("name", ""), "args": entry.get("args") or {}}
    return {"name": str(entry), "args": {}}


def _norm_turn_trace(raw: dict) -> dict:
    return {
        "input": raw.get("input") or raw.get("utterance") or "",
        "intent": raw.get("intent", raw.get("predicted")),
        "tools": [_norm_tool(t) for t in (raw.get("tools") or raw.get("tool_calls") or [])],
        "answer": raw.get("answer") or raw.get("response") or "",
        "latency_ms": raw.get("latency_ms"),
        "cost_usd": raw.get("cost_usd"),
        "escalated": raw.get("escalated", raw.get("escalate")),
    }


def normalize_trace(raw: dict) -> dict:
    escalated = raw.get("escalated", raw.get("escalate"))
    turns = [_norm_turn_trace(t) for t in (raw.get("turns") or [])]
    tools = [_norm_tool(t) for t in (raw.get("tools") or raw.get("tool_calls") or [])]
    latency = raw.get("latency_ms")
    cost = raw.get("cost_usd")
    answer = raw.get("answer") or raw.get("response") or ""
    intent = raw.get("intent", raw.get("predicted"))
    if turns:
        if not tools:
            tools = [tool for turn in turns for tool in turn["tools"]]
        if latency is None:
            vals = [t["latency_ms"] for t in turns if t["latency_ms"] is not None]
            latency = sum(vals) if vals else None
        if cost is None:
            vals = [t["cost_usd"] for t in turns if t["cost_usd"] is not None]
            cost = round(sum(vals), 6) if vals else None
        if not answer:
            answer = turns[-1]["answer"]
        if intent is None:
            intent = turns[-1]["intent"]
        if escalated is None:
            escalated = any(bool(t["escalated"]) for t in turns)
    return {
        "id": raw.get("id"),
        "input": raw.get("input") or raw.get("utterance") or "",
        "intent": intent,
        "flow": raw.get("flow"),
        "tools": tools,
        "answer": answer,
        "latency_ms": latency,
        "cost_usd": cost,
        "escalated": escalated,
        "judge_score": raw.get("judge_score"),
        "judge_rationale": raw.get("judge_rationale"),
        "turns": turns,
    }


def load_traces(path) -> list[dict]:
    path = Path(path)
    traces = []
    with open(path, encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as e:
                raise SystemExit(f"{path}:{line_no}: invalid JSON — {e}")
            traces.append(normalize_trace(raw))
    return traces


def index_traces(traces: list[dict]) -> dict:
    """Index traces by id first, then by input text."""
    by_key = {}
    for t in traces:
        if t.get("id"):
            by_key[f"id:{t['id']}"] = t
        if t.get("input"):
            by_key.setdefault(f"in:{t['input']}", t)
    return by_key


def find_trace(index: dict, case: dict):
    return index.get(f"id:{case['id']}") or index.get(f"in:{case['input']}")


def run_cases_against_endpoint(cases: list[dict], url: str, timeout: int = 60) -> list[dict]:
    """POST each case input to an agent endpoint and collect its trace.

    The endpoint receives ``{"id": ..., "input": ...}`` and should return
    a JSON trace object (see module docstring). This keeps the harness
    agent-agnostic: any framework can be evaluated through one adapter.
    """
    traces = []
    for case in cases:
        payload = json.dumps({"id": case["id"], "input": case["input"]}).encode("utf-8")
        req = urllib.request.Request(
            url, data=payload, headers={"Content-Type": "application/json"}, method="POST"
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
        trace = normalize_trace(raw)
        trace.setdefault("id", case["id"])
        if not trace.get("id"):
            trace["id"] = case["id"]
        traces.append(trace)
    return traces
