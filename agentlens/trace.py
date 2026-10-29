"""Load recorded agent runs (\"traces\") from a JSONL file, or collect them
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

Enhancement changes (v0.3):
- ``run_cases_against_endpoint`` is now fault-tolerant: per-request errors
  produce a sentinel trace instead of crashing the whole evaluation.
- Supports concurrent requests via ``concurrency`` parameter to speed up
  large test suites against live agent endpoints.
- ``normalize_trace`` guards against ``None`` args on tool calls, normalising
  them to ``{}`` so scoring never throws a TypeError.
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
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
            return {"name": fn.get("name", ""), "args": args if isinstance(args, dict) else {}}
        raw_args = entry.get("args") or {}
        return {"name": entry.get("name", ""), "args": raw_args if isinstance(raw_args, dict) else {}}
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


def _error_trace(case: dict, error: str) -> dict:
    """Produce a sentinel trace for a case that could not be fetched.

    This trace will score as a missing-trace failure with a clear error
    message rather than crashing the whole evaluation run.
    """
    return {
        "id": case["id"],
        "input": case["input"],
        "intent": None,
        "flow": None,
        "tools": [],
        "answer": "",
        "latency_ms": None,
        "cost_usd": None,
        "escalated": None,
        "judge_score": None,
        "judge_rationale": None,
        "turns": [],
        "_error": error,
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


def _fetch_one(case: dict, url: str, timeout: int) -> dict:
    """POST a single case to the agent endpoint and return its normalised trace.

    Returns an error sentinel trace on any failure so the caller can continue
    evaluating remaining cases.
    """
    payload = json.dumps({"id": case["id"], "input": case["input"]}).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.status
            raw_bytes = resp.read()
    except urllib.error.HTTPError as exc:
        return _error_trace(case, f"HTTP {exc.code} from agent endpoint: {exc.reason}")
    except urllib.error.URLError as exc:
        return _error_trace(case, f"connection error reaching agent endpoint: {exc.reason}")
    except TimeoutError:
        return _error_trace(case, f"agent endpoint timed out after {timeout}s")
    except Exception as exc:  # noqa: BLE001
        return _error_trace(case, f"unexpected error: {exc}")

    if status != 200:
        return _error_trace(case, f"agent returned HTTP {status}")

    try:
        raw = json.loads(raw_bytes.decode("utf-8"))
    except json.JSONDecodeError as exc:
        return _error_trace(case, f"agent returned invalid JSON: {exc}")

    trace = normalize_trace(raw)
    if not trace.get("id"):
        trace["id"] = case["id"]
    return trace


def run_cases_against_endpoint(
    cases: list[dict],
    url: str,
    timeout: int = 60,
    concurrency: int = 1,
) -> list[dict]:
    """POST each case to an agent endpoint and collect its trace.

    The endpoint receives ``{"id": ..., "input": ...}`` and should return
    a JSON trace object (see module docstring). This keeps the harness
    agent-agnostic: any framework can be evaluated through one adapter.

    Args:
        cases:       Normalised case dicts from ``load_cases``.
        url:         HTTP(S) endpoint URL.
        timeout:     Per-request timeout in seconds (default 60).
        concurrency: Number of parallel requests (default 1 = sequential).
                     Increase to speed up evaluation against fast agents.
                     Use ``--concurrency`` on the CLI.

    Returns:
        List of trace dicts in the **same order** as ``cases``. Failed
        requests produce an error-sentinel trace instead of raising so that
        the rest of the evaluation can still complete.
    """
    if concurrency < 1:
        concurrency = 1

    # Sequential path (default) — preserves order, no threading overhead.
    if concurrency == 1:
        traces = []
        for idx, case in enumerate(cases, 1):
            trace = _fetch_one(case, url, timeout)
            if "_error" in trace:
                print(
                    f"  [warn] case {case['id']!r} ({idx}/{len(cases)}): {trace['_error']}",
                    file=sys.stderr,
                )
            traces.append(trace)
        return traces

    # Concurrent path — preserves original case order in output.
    results: dict[int, dict] = {}
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = {pool.submit(_fetch_one, case, url, timeout): i for i, case in enumerate(cases)}
        for future in as_completed(futures):
            idx = futures[future]
            case = cases[idx]
            try:
                trace = future.result()
            except Exception as exc:  # noqa: BLE001
                trace = _error_trace(case, f"unexpected executor error: {exc}")
            if "_error" in trace:
                print(
                    f"  [warn] case {case['id']!r}: {trace['_error']}",
                    file=sys.stderr,
                )
            results[idx] = trace

    return [results[i] for i in range(len(cases))]
