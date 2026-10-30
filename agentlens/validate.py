"""Validate datasets and trace files before running an evaluation.

Catches the boring mistakes that otherwise look like agent failures:
duplicate case ids, empty inputs, tool expectations without a name,
judge thresholds outside 0..1, traces that match no case.
"""
from __future__ import annotations

KNOWN_CASE_FIELDS = {
    "id", "input", "utterance", "expected", "expected_intent", "expect_flow",
    "expected_flow", "expect_not", "expected_tools", "expected_tools_mode",
    "forbidden_tools", "expected_answer_contains", "should_escalate",
    "expected_escalation", "max_latency_ms", "max_cost_usd", "max_tool_calls",
    "judge", "turns", "tags",
    "max_steps", "expect_efficient", "forbid_pii", "forbid_leak",
    "rag", "expected_context", "source", "needs_review",
}


def validate_cases(raw_cases: list[dict], cases: list[dict]) -> list[str]:
    issues = []
    seen_ids = {}
    for raw, case in zip(raw_cases, cases):
        cid = case["id"]
        if cid in seen_ids:
            issues.append(f"duplicate case id: {cid} (lines {seen_ids[cid]} and its repeat)")
        seen_ids.setdefault(cid, True)
        unknown = set(raw.keys()) - KNOWN_CASE_FIELDS
        if unknown:
            issues.append(f"{cid}: unknown field(s) {sorted(unknown)} — typo?")
        if not case["input"] and not case["turns"]:
            issues.append(f"{cid}: empty input")
        for tool in case["expected_tools"]:
            if not tool["name"]:
                issues.append(f"{cid}: expected_tools entry without a name")
        if case["expected_tools_mode"] not in ("exact", "subsequence"):
            issues.append(f"{cid}: expected_tools_mode must be 'exact' or 'subsequence'")
        if case["judge"] is not None and not (0.0 <= case["judge"]["min_score"] <= 1.0):
            issues.append(f"{cid}: judge min_score must be between 0 and 1")
        if case["max_tool_calls"] is not None and case["max_tool_calls"] < 1:
            issues.append(f"{cid}: max_tool_calls must be >= 1")
        for idx, turn in enumerate(case["turns"]):
            if not turn["input"]:
                issues.append(f"{cid}: turn {idx + 1} has an empty input")
    return issues


def validate_traces(cases: list[dict], traces: list[dict]) -> list[str]:
    issues = []
    case_ids = {c["id"] for c in cases}
    case_inputs = {c["input"] for c in cases}
    matched = set()
    for t in traces:
        key = t.get("id") or t.get("input")
        if t.get("id") and t["id"] in case_ids:
            matched.add(t["id"])
        elif t.get("input") in case_inputs:
            matched.add(t["input"])
        else:
            issues.append(f"trace matches no case: {key!r}")
    for c in cases:
        if c["id"] not in matched and c["input"] not in matched:
            issues.append(f"case has no trace: {c['id']}")
    return issues
