"""Load and normalise evaluation cases from a JSONL dataset.

Two case styles are supported:

1. Agent-task cases (full format)::

    {"id": "refund-1", "input": "I want a refund",
     "expected_intent": "refund_request",
     "expected_tools": [{"name": "lookup_order", "args_contains": {"id": "A1"}}],
     "forbidden_tools": ["issue_payment"],
     "expected_answer_contains": ["refund"],
     "should_escalate": false,
     "max_latency_ms": 3000, "max_cost_usd": 0.02,
     "tags": ["billing"]}

2. Intent cases (compatible with simple intent-classifier eval sets)::

    {"utterance": "talk to a human", "expected": "contact_human",
     "expect_flow": "book_callback", "expect_not": ["place_order"]}

``expected: "any"`` means no intent is asserted — only the negative
(``expect_not``) assertions are checked.
"""
from __future__ import annotations

import json
from pathlib import Path


def _norm_tool(entry):
    if isinstance(entry, str):
        return {"name": entry, "args_contains": {}}
    if isinstance(entry, dict):
        args = entry.get("args_contains") or entry.get("args") or {}
        return {"name": entry.get("name", ""), "args_contains": args}
    return {"name": str(entry), "args_contains": {}}


def _norm_turn(raw: dict) -> dict:
    expected = raw.get("expected_intent", raw.get("expected"))
    if expected == "any":
        expected = None
    return {
        "input": raw.get("input") or raw.get("utterance") or "",
        "expected_intent": expected,
        "expected_tools": [_norm_tool(t) for t in (raw.get("expected_tools") or [])],
    }


def _norm_judge(raw) -> dict | None:
    if not raw:
        return None
    if isinstance(raw, str):
        return {"criteria": raw, "min_score": 0.7}
    return {
        "criteria": raw.get("criteria", ""),
        "min_score": float(raw.get("min_score", 0.7)),
    }


def normalize_case(raw: dict, line_no: int) -> dict:
    turns = [_norm_turn(t) for t in (raw.get("turns") or [])]
    text = raw.get("input") or raw.get("utterance") or (turns[0]["input"] if turns else "")
    expected = raw.get("expected_intent", raw.get("expected"))
    if expected == "any":
        expected = None
    contains = raw.get("expected_answer_contains") or []
    if isinstance(contains, str):
        contains = [contains]
    should_escalate = raw.get("should_escalate")
    if should_escalate is None and raw.get("expected_escalation") is not None:
        should_escalate = raw.get("expected_escalation")
    return {
        "id": str(raw.get("id") or f"case-{line_no:03d}"),
        "input": text,
        "expected_intent": expected,
        "expect_flow": raw.get("expect_flow") or raw.get("expected_flow"),
        "expect_not": list(raw.get("expect_not") or []),
        "expected_tools": [_norm_tool(t) for t in (raw.get("expected_tools") or [])],
        "expected_tools_mode": raw.get("expected_tools_mode", "exact"),
        "forbidden_tools": list(raw.get("forbidden_tools") or []),
        "expected_answer_contains": list(contains),
        "should_escalate": should_escalate,
        "max_latency_ms": raw.get("max_latency_ms"),
        "max_cost_usd": raw.get("max_cost_usd"),
        "max_tool_calls": raw.get("max_tool_calls"),
        "judge": _norm_judge(raw.get("judge")),
        "turns": turns,
        "tags": list(raw.get("tags") or []),
    }


def load_cases(path) -> list[dict]:
    path = Path(path)
    cases = []
    with open(path, encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as e:
                raise SystemExit(f"{path}:{line_no}: invalid JSON — {e}")
            cases.append(normalize_case(raw, line_no))
    if not cases:
        raise SystemExit(f"{path}: no cases found")
    return cases
