"""Command line interface.

Examples:
    python -m agentlens demo
    python -m agentlens run --cases examples/cases.jsonl --traces examples/traces.sample.jsonl --out reports/run1
    python -m agentlens run --cases examples/cases.jsonl --endpoint http://localhost:9000/eval --out reports/run2 --min-success 90
    python -m agentlens compare reports/run1/report.json reports/run2/report.json --fail-on-regression 0
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .adapters import convert_langchain, otel_document_to_traces
from .bench import render_benchmark, run_benchmark
from .compare import build_trend, compare_reports, load_report, render_comparison, render_trend
from .dataset import load_cases
from .generate import generate_dataset
from .judge import build_judge
from .monitor import run_monitor
from .report import build_report, write_reports
from .scoring import score_case
from .server import serve
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


def _stability(all_results: list[list[dict]], runs: int) -> dict:
    per_case: dict[str, dict] = {}
    for results in all_results:
        for row in results:
            entry = per_case.setdefault(row["id"], {"passed": 0, "runs": 0})
            entry["runs"] += 1
            entry["passed"] += 1 if row["passed"] else 0
    for entry in per_case.values():
        entry["pass_rate"] = round(entry["passed"] / entry["runs"], 4) if entry["runs"] else 0.0
    flaky = [cid for cid, e in per_case.items() if 0 < e["pass_rate"] < 1]
    return {"runs": runs, "per_case": per_case, "flaky_cases": flaky}


def cmd_run(args) -> int:
    cases = load_cases(args.cases)
    judge = build_judge(args.judge, endpoint=args.judge_endpoint, model=args.judge_model,
                        api_key_env=args.judge_api_key_env)
    repeat = getattr(args, "repeat", 1) or 1
    if args.endpoint:
        source = f"endpoint {args.endpoint}"
        if repeat > 1:
            all_results = []
            report = None
            for _ in range(repeat):
                traces = run_cases_against_endpoint(cases, args.endpoint, timeout=args.timeout)
                index = index_traces(traces)
                results = [score_case(c, find_trace(index, c), judge=judge) for c in cases]
                all_results.append(results)
                report = build_report(results, {"dataset": str(args.cases), "source": source})
            report["stability"] = _stability(all_results, repeat)
            paths = write_reports(report, args.out)
            s = report["summary"]
            print(f"Task success (final run): {s['task_success_rate']}% ({s['passed']}/{s['total_cases']}) over {repeat} repeated runs")
            print(f"Flaky cases: {report['stability']['flaky_cases'] or 'none'}")
            for kind, path in paths.items():
                print(f"  {kind}: {path}")
            if args.min_success is not None and s["task_success_rate"] < args.min_success:
                print(f"GATE FAILED: task success {s['task_success_rate']}% < required {args.min_success}%", file=sys.stderr)
                return 1
            return 0
        traces = run_cases_against_endpoint(cases, args.endpoint, timeout=args.timeout)
    elif args.traces:
        traces = load_traces(args.traces)
        source = f"traces {args.traces}"
        if repeat > 1:
            print("note: --repeat with recorded traces is deterministic; stability needs a live --endpoint", file=sys.stderr)
    else:
        print("error: provide --traces FILE or --endpoint URL", file=sys.stderr)
        return 2
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


def cmd_bench(args) -> int:
    cases = load_cases(args.cases)
    configs = {}
    for spec in args.config:
        if "=" not in spec:
            print(f"error: --config expects NAME=traces.jsonl, got {spec!r}", file=sys.stderr)
            return 2
        name, path = spec.split("=", 1)
        configs[name] = load_traces(path)
    bench = run_benchmark(cases, configs)
    text = render_benchmark(bench)
    print(text)
    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / "bench.md").write_text(text, encoding="utf-8")
        (out / "bench.json").write_text(json.dumps(bench, indent=2), encoding="utf-8")
        print(f"written: {out}/bench.md, {out}/bench.json")
    return 0


def cmd_generate(args) -> int:
    cases = load_cases(args.cases)
    generated = generate_dataset(cases)
    with open(args.out, "w", encoding="utf-8") as f:
        for case in generated:
            f.write(json.dumps(case) + "\n")
    print(f"Generated {len(generated)} synthetic candidate case(s) → {args.out}")
    print("Every generated case is stamped source=synthetic, needs_review=true — review expectations before use.")
    return 0


def cmd_convert(args) -> int:
    raw = json.loads(Path(args.infile).read_text(encoding="utf-8"))
    if args.format == "langchain":
        records = raw if isinstance(raw, list) else [raw]
        traces = convert_langchain(records)
    else:  # otel
        traces = otel_document_to_traces(raw)
    from .trace import normalize_trace
    with open(args.out, "w", encoding="utf-8") as f:
        for trace in traces:
            f.write(json.dumps(normalize_trace(trace)) + "\n")
    print(f"Converted {len(traces)} trace(s) from {args.format} → {args.out}")
    return 0


def cmd_serve(args) -> int:
    serve(args.host, args.port)
    return 0


def cmd_monitor(args) -> int:
    cases = load_cases(args.cases)
    if args.endpoint:
        traces = run_cases_against_endpoint(cases, args.endpoint, timeout=args.timeout)
        source = f"endpoint {args.endpoint}"
    elif args.traces:
        traces = load_traces(args.traces)
        source = f"traces {args.traces}"
    else:
        print("error: provide --traces FILE or --endpoint URL", file=sys.stderr)
        return 2
    report = _evaluate(cases, traces, {"dataset": str(args.cases), "source": source})
    result = run_monitor(report, args.history, alert_below=args.alert_below, max_drop=args.max_drop)
    entry = result["entry"]
    print(f"Monitor: task success {entry['task_success_rate']}% ({entry['passed']}/{entry['total_cases']}) — recorded to {args.history}")
    for alert in result["alerts"]:
        print(f"ALERT: {alert}", file=sys.stderr)
    return 2 if result["alerts"] else 0


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
    p_run.add_argument("--out", default="reports/run", help="Output directory for reports")
    p_run.add_argument("--min-success", type=float, default=None, help="Exit 1 if task success rate is below this percent (CI gate)")
    p_run.add_argument("--judge", choices=["none", "heuristic", "openai"], default="none",
                       help="LLM-as-judge for cases with a 'judge' block (a trace judge_score always wins)")
    p_run.add_argument("--judge-endpoint", help="OpenAI-compatible base URL, e.g. http://localhost:11434/v1")
    p_run.add_argument("--judge-model", help="Judge model name for --judge openai")
    p_run.add_argument("--judge-api-key-env", default="JUDGE_API_KEY", help="Env var holding the judge API key")
    p_run.add_argument("--repeat", type=int, default=1, help="Repeat a live --endpoint run N times and report per-case stability/flakiness")
    p_run.set_defaults(func=cmd_run)

    p_bench = sub.add_parser("bench", help="Benchmark several configurations (models/prompts) on the same dataset")
    p_bench.add_argument("--cases", required=True)
    p_bench.add_argument("--config", action="append", required=True, help="NAME=traces.jsonl (repeatable)")
    p_bench.add_argument("--out", help="Also write bench.md and bench.json to this directory")
    p_bench.set_defaults(func=cmd_bench)

    p_gen = sub.add_parser("generate", help="Generate synthetic candidate cases (stamped needs_review) from a dataset")
    p_gen.add_argument("--cases", required=True)
    p_gen.add_argument("--out", required=True, help="Output JSONL path for the generated cases")
    p_gen.set_defaults(func=cmd_generate)

    p_conv = sub.add_parser("convert", help="Convert LangChain-style records or OpenTelemetry spans into AgentLens traces")
    p_conv.add_argument("--format", choices=["langchain", "otel"], required=True)
    p_conv.add_argument("--in", dest="infile", required=True)
    p_conv.add_argument("--out", required=True, help="Output traces JSONL path")
    p_conv.set_defaults(func=cmd_convert)

    p_serve = sub.add_parser("serve", help="Serve the HTTP API (POST /evaluate, GET /health) on localhost")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8765)
    p_serve.set_defaults(func=cmd_serve)

    p_mon = sub.add_parser("monitor", help="Run an evaluation, append it to a history file, and alert on drops")
    p_mon.add_argument("--cases", required=True)
    p_mon.add_argument("--traces")
    p_mon.add_argument("--endpoint")
    p_mon.add_argument("--timeout", type=int, default=60)
    p_mon.add_argument("--history", default="reports/monitor-history.jsonl")
    p_mon.add_argument("--alert-below", type=float, default=None, help="Alert (exit 2) if task success falls below this percent")
    p_mon.add_argument("--max-drop", type=float, default=None, help="Alert (exit 2) if task success drops more than this many points vs the previous run")
    p_mon.set_defaults(func=cmd_monitor)

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
