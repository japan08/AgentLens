"""Validate datasets and trace files before running an evaluation.

Catches the boring mistakes that otherwise look like agent failures:
duplicate case ids, empty inputs, tool expectations without a name,
judge thresholds outside 0..1, traces that match no case.

Enhancement (v0.3): validate_traces now also checks trace field *types*
so that ``"latency_ms": "fast"`` or ``"escalated": "yes"`` are caught
before they silently corrupt scoring metrics.
"""
from __future__ import annotations

KNOWN_CASE_FIELDS = {
    "id", "input", "utterance", "expected", "expected_intent", "expect_flow",
    "expected_flow", "expect_not", "expected_tools", "expected_tools_mode",
    "forbidden_tools", "expected_answer_contains", "should_escalate",
    "expected_escalation", "max_latency_ms", "max_cost_usd", "max_tool_calls",
    "judge", "turns", "tags",
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


def _validate_trace_schema(trace: dict) -> list[str]:
    """Validate the types of fields in a single normalised trace.

    Returns a list of human-readable issue strings (empty = valid).
    """
    issues = []
    tid = trace.get("id") or trace.get("input") or "<unknown>"

    latency = trace.get("latency_ms")
    if latency is not None and not isinstance(latency, (int, float)):
        issues.append(
            f"trace {tid!r}: latency_ms must be a number, "
            f"got {type(latency).__name__!r} ({latency!r})"
        )

    cost = trace.get("cost_usd")
    if cost is not None and not isinstance(cost, (int, float)):
        issues.append(
            f"trace {tid!r}: cost_usd must be a number, "
            f"got {type(cost).__name__!r} ({cost!r})"
        )

    escalated = trace.get("escalated")
    if escalated is not None and not isinstance(escalated, bool):
        issues.append(
            f"trace {tid!r}: escalated must be a boolean (true/false), "
            f"got {type(escalated).__name__!r} ({escalated!r})"
        )

    tools = trace.get("tools")
    if tools is not None:
        if not isinstance(tools, list):
            issues.append(
                f"trace {tid!r}: tools must be a list, got {type(tools).__name__!r}"
            )
        else:
            for i, tool in enumerate(tools):
                if not isinstance(tool, dict):
                    issues.append(
                        f"trace {tid!r}: tools[{i}] must be a dict, "
                        f"got {type(tool).__name__!r}"
                    )
                    continue
                if not isinstance(tool.get("name", ""), str):
                    issues.append(f"trace {tid!r}: tools[{i}].name must be a string")
                args = tool.get("args")
                if args is not None and not isinstance(args, dict):
                    issues.append(
                        f"trace {tid!r}: tools[{i}].args must be a dict or null, "
                        f"got {type(args).__name__!r}"
                    )

    judge_score = trace.get("judge_score")
    if judge_score is not None and not isinstance(judge_score, (int, float)):
        issues.append(
            f"trace {tid!r}: judge_score must be a number, "
            f"got {type(judge_score).__name__!r}"
        )
    elif judge_score is not None and not (0.0 <= float(judge_score) <= 1.0):
        issues.append(f"trace {tid!r}: judge_score {judge_score} is outside [0, 1]")

    return issues


def validate_traces(cases: list[dict], traces: list[dict]) -> list[str]:
    issues = []
    case_ids = {c["id"] for c in cases}
    case_inputs = {c["input"] for c in cases}
    matched = set()
    for t in traces:
        # Schema / type validation (new in v0.3)
        issues.extend(_validate_trace_schema(t))

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
