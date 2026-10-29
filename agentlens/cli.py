"""Command line interface.

Examples:
    python -m agentlens demo
    python -m agentlens run --cases examples/cases.jsonl --traces examples/traces.sample.jsonl --out reports/run1
    python -m agentlens run --cases examples/cases.jsonl --endpoint http://localhost:9000/eval --out reports/run2 --min-success 90
    python -m agentlens compare reports/run1/report.json reports/run2/report.json --fail-on-regression 0
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .compare import build_trend, compare_reports, load_report, render_comparison, render_trend
from .dataset import load_cases
from .judge import build_judge
from .report import build_report, write_reports
from .scoring import score_case
from .trace import find_trace, index_traces, load_traces, run_cases_against_endpoint
from .validate import validate_cases, validate_traces

ROOT = Path(__file__).resolve().parents[1]


def _evaluate(cases, traces, meta, judge=None):
    index = index_traces(traces)
    results = [score_case(case, find_trace(index, case), judge=judge) for case in cases]
    return build_report(results, meta)


def cmd_demo(args) -> int:
    cases = load_cases(ROOT / "examples" / "cases.jsonl")
    traces = load_traces(ROOT / "examples" / "traces.sample.jsonl")
    report = _evaluate(cases, traces, {"dataset": "examples/cases.jsonl", "source": "sample traces"})
    paths = write_reports(report, args.out)
    s = report["summary"]
    print(f"Demo run: {s['passed']}/{s['total_cases']} cases passed — task success {s['task_success_rate']}%")
    for kind, path in paths.items():
        print(f"  {kind}: {path}")
    return 0


def cmd_run(args) -> int:
    cases = load_cases(args.cases)
    if args.endpoint:
        traces = run_cases_against_endpoint(
            cases, args.endpoint,
            timeout=args.timeout,
            concurrency=args.concurrency,
        )
        source = f"endpoint {args.endpoint}"
    elif args.traces:
        traces = load_traces(args.traces)
        source = f"traces {args.traces}"
    else:
        print("error: provide --traces FILE or --endpoint URL", file=sys.stderr)
        return 2
    judge = build_judge(args.judge, endpoint=args.judge_endpoint, model=args.judge_model,
                        api_key_env=args.judge_api_key_env)
    report = _evaluate(cases, traces, {"dataset": str(args.cases), "source": source}, judge=judge)
    paths = write_reports(report, args.out)
    s = report["summary"]
    print(f"Task success: {s['task_success_rate']}% ({s['passed']}/{s['total_cases']})")
    print(f"Intent accuracy: {s['intent_accuracy']} · Tool sequence: {s['tool_sequence_accuracy']} · Tool args: {s['tool_args_accuracy']}")
    print(f"Avg latency: {s['avg_latency_ms']} ms · Cost per success: {s['cost_per_success_usd']} USD")
    for kind, path in paths.items():
        print(f"  {kind}: {path}")
    if args.min_success is not None and s["task_success_rate"] < args.min_success:
        print(f"GATE FAILED: task success {s['task_success_rate']}% < required {args.min_success}%", file=sys.stderr)
        return 1
    return 0


def cmd_validate(args) -> int:
    import json as _json
    raw_cases = []
    with open(args.cases, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                raw_cases.append(_json.loads(line))
    cases = load_cases(args.cases)
    issues = validate_cases(raw_cases, cases)
    if args.traces:
        issues += validate_traces(cases, load_traces(args.traces))
    if issues:
        print(f"Found {len(issues)} issue(s):")
        for issue in issues:
            print(f"  - {issue}")
        return 1
    print(f"OK: {len(cases)} case(s) valid" + (", traces matched" if args.traces else ""))
    return 0


def cmd_trend(args) -> int:
    rows = build_trend([load_report(p) for p in args.reports])
    text = render_trend(rows)
    print(text)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"written: {args.out}")
    return 0


def cmd_compare(args) -> int:
    comp = compare_reports(load_report(args.old), load_report(args.new))
    text = render_comparison(comp)
    print(text)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"written: {args.out}")
    delta = comp["success_rate_delta"]
    if args.fail_on_regression is not None and delta is not None and delta < -abs(args.fail_on_regression):
        print(f"REGRESSION: success rate dropped by {-delta}% (allowed {args.fail_on_regression}%)", file=sys.stderr)
        return 1
    if comp["newly_failing"] and args.fail_on_any_new_failure:
        print(f"REGRESSION: newly failing cases: {comp['newly_failing']}", file=sys.stderr)
        return 1
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="agentlens", description="Evaluate AI agents on task success, tool calls, escalation, latency and cost.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_demo = sub.add_parser("demo", help="Run the bundled sample dataset against sample traces")
    p_demo.add_argument("--out", default=str(ROOT / "reports" / "demo"), help="Output directory for reports")
    p_demo.set_defaults(func=cmd_demo)

    p_run = sub.add_parser("run", help="Evaluate cases against recorded traces or a live HTTP endpoint")
    p_run.add_argument("--cases", required=True, help="JSONL dataset of evaluation cases")
    p_run.add_argument("--traces", help="JSONL file of recorded agent traces")
    p_run.add_argument("--endpoint", help="HTTP endpoint that accepts {id, input} and returns a trace JSON")
    p_run.add_argument("--timeout", type=int, default=60, help="Per-request timeout for --endpoint (seconds)")
    p_run.add_argument("--concurrency", type=int, default=1, help="Parallel requests for --endpoint (default: 1 = sequential)")
    p_run.add_argument("--out", default="reports/run", help="Output directory for reports")
    p_run.add_argument("--min-success", type=float, default=None, help="Exit 1 if task success rate is below this percent (CI gate)")
    p_run.add_argument("--judge", choices=["none", "heuristic", "openai"], default="none",
                       help="LLM-as-judge for cases with a 'judge' block (a trace judge_score always wins)")
    p_run.add_argument("--judge-endpoint", help="OpenAI-compatible base URL, e.g. http://localhost:11434/v1")
    p_run.add_argument("--judge-model", help="Judge model name for --judge openai")
    p_run.add_argument("--judge-api-key-env", default="JUDGE_API_KEY", help="Env var holding the judge API key")
    p_run.set_defaults(func=cmd_run)

    p_val = sub.add_parser("validate", help="Check a dataset (and optionally traces) for mistakes before running")
    p_val.add_argument("--cases", required=True)
    p_val.add_argument("--traces", help="Also check that traces and cases match")
    p_val.set_defaults(func=cmd_validate)

    p_trend = sub.add_parser("trend", help="Tabulate metrics across several report.json files, oldest first")
    p_trend.add_argument("reports", nargs="+")
    p_trend.add_argument("--out", help="Also write the trend table as Markdown to this path")
    p_trend.set_defaults(func=cmd_trend)

    p_cmp = sub.add_parser("compare", help="Diff two report.json files to catch regressions")
    p_cmp.add_argument("old")
    p_cmp.add_argument("new")
    p_cmp.add_argument("--out", help="Also write the comparison as Markdown to this path")
    p_cmp.add_argument("--fail-on-regression", type=float, default=None, help="Exit 1 if success rate drops by more than this many points")
    p_cmp.add_argument("--fail-on-any-new-failure", action="store_true", help="Exit 1 if any case newly fails")
    p_cmp.set_defaults(func=cmd_compare)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
