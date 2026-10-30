import json
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agentlens.compare import compare_reports
from agentlens.dataset import normalize_case
from agentlens.report import build_report
from agentlens.scoring import aggregate, score_case
from agentlens.trace import normalize_trace, run_cases_against_endpoint


def make_case(**overrides):
    base = {
        "id": "c1",
        "input": "where is my order A1",
        "expected_intent": "order_status",
        "expect_flow": None,
        "expect_not": [],
        "expected_tools": [{"name": "lookup_order", "args_contains": {"id": "A1"}}],
        "forbidden_tools": [],
        "expected_answer_contains": [],
        "should_escalate": None,
        "max_latency_ms": None,
        "max_cost_usd": None,
        "tags": ["orders"],
    }
    base.update(overrides)
    return base


def make_trace(**overrides):
    base = {
        "id": "c1",
        "input": "where is my order A1",
        "intent": "order_status",
        "flow": None,
        "tools": [{"name": "lookup_order", "args": {"id": "A1"}}],
        "answer": "On its way",
        "latency_ms": 500,
        "cost_usd": 0.001,
        "escalated": False,
    }
    base.update(overrides)
    return base


class TestDataset(unittest.TestCase):
    def test_intent_style_case_any_means_no_intent_assertion(self):
        case = normalize_case(
            {"utterance": "buy now", "expected": "any", "expect_not": ["buy_now"]}, 1
        )
        self.assertEqual(case["input"], "buy now")
        self.assertIsNone(case["expected_intent"])
        self.assertEqual(case["expect_not"], ["buy_now"])

    def test_tool_string_normalises(self):
        case = normalize_case({"input": "x", "expected_tools": ["search"]}, 2)
        self.assertEqual(case["expected_tools"], [{"name": "search", "args_contains": {}}])


class TestScoring(unittest.TestCase):
    def test_passing_case(self):
        result = score_case(make_case(), make_trace())
        self.assertTrue(result["passed"])

    def test_wrong_tool_argument_fails_args_but_not_sequence(self):
        trace = make_trace(tools=[{"name": "lookup_order", "args": {"id": "A2"}}])
        result = score_case(make_case(), trace)
        self.assertFalse(result["passed"])
        self.assertTrue(result["checks"]["tool_sequence"])
        self.assertFalse(result["checks"]["tool_args"])

    def test_forbidden_intent_leak_fails(self):
        case = make_case(expected_intent=None, expect_not=["place_order"], expected_tools=[])
        result = score_case(case, make_trace(intent="place_order", tools=[]))
        self.assertFalse(result["passed"])
        self.assertFalse(result["checks"]["forbidden_intent"])

    def test_missed_escalation_fails(self):
        case = make_case(should_escalate=True, expected_tools=[])
        result = score_case(case, make_trace(escalated=False, tools=[]))
        self.assertFalse(result["passed"])
        self.assertFalse(result["checks"]["escalation"])

    def test_missing_trace_fails(self):
        result = score_case(make_case(), None)
        self.assertFalse(result["passed"])

    def test_aggregate_cost_per_success(self):
        results = [score_case(make_case(), make_trace()),
                   score_case(make_case(id="c2"), make_trace(id="c2", intent="wrong"))]
        summary = aggregate(results)
        self.assertEqual(summary["total_cases"], 2)
        self.assertEqual(summary["passed"], 1)
        self.assertAlmostEqual(summary["cost_per_success_usd"], 0.002)


class TestCompare(unittest.TestCase):
    def test_regression_detection(self):
        old = build_report([score_case(make_case(), make_trace())], {})
        new = build_report([score_case(make_case(), make_trace(intent="wrong"))], {})
        comp = compare_reports(old, new)
        self.assertEqual(comp["newly_failing"], ["c1"])
        self.assertEqual(comp["success_rate_delta"], -100.0)


class _Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        trace = {
            "id": body.get("id"),
            "intent": "order_status",
            "tools": [{"name": "lookup_order", "args": {"id": "A1"}}],
            "answer": "On its way",
            "latency_ms": 100,
            "cost_usd": 0.001,
            "escalated": False,
        }
        payload = json.dumps(trace).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass


class TestEndpointRunner(unittest.TestCase):
    def test_http_runner_collects_traces(self):
        server = HTTPServer(("127.0.0.1", 0), _Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_address[1]}/eval"
            traces = run_cases_against_endpoint([make_case()], url, timeout=5)
        finally:
            server.shutdown()
        self.assertEqual(len(traces), 1)
        result = score_case(make_case(), normalize_trace(traces[0]) if isinstance(traces[0], dict) else traces[0])
        self.assertTrue(result["passed"])


from agentlens.dataset import normalize_case as _nc  # noqa: E402
from agentlens.judge import HeuristicJudge, OpenAICompatibleJudge  # noqa: E402
from agentlens.trace import normalize_trace as _nt  # noqa: E402
from agentlens.validate import validate_cases  # noqa: E402
from agentlens.compare import build_trend  # noqa: E402


class TestAdvancedScoring(unittest.TestCase):
    def test_subsequence_mode_allows_extra_tools(self):
        case = make_case(expected_tools_mode="subsequence")
        trace = make_trace(tools=[{"name": "get_session", "args": {}},
                                  {"name": "lookup_order", "args": {"id": "A1"}}])
        result = score_case(case, trace)
        self.assertTrue(result["checks"]["tool_sequence"])
        self.assertTrue(result["checks"]["tool_args"])
        self.assertTrue(result["passed"])

    def test_tool_budget_and_loop_guard(self):
        case = make_case(expected_tools=[], max_tool_calls=2)
        trace = make_trace(tools=[{"name": "ping", "args": {}}] * 3)
        result = score_case(case, trace)
        self.assertFalse(result["checks"]["tool_budget"])
        self.assertFalse(result["checks"]["tool_loop"])
        self.assertFalse(result["passed"])

    def test_multi_turn_case(self):
        case = _nc({
            "id": "mt",
            "turns": [
                {"input": "order missing", "expected_intent": "order_status",
                 "expected_tools": [{"name": "lookup_order", "args_contains": {"id": "A9"}}]},
                {"input": "refund it", "expected_intent": "refund_request",
                 "expected_tools": [{"name": "create_refund", "args_contains": {"order_id": "A9"}}]},
            ],
            "expected_answer_contains": ["refund started"],
            "should_escalate": False,
        }, 1)
        trace = _nt({
            "id": "mt",
            "turns": [
                {"intent": "order_status", "tools": [{"name": "lookup_order", "args": {"id": "A9"}}],
                 "answer": "No delivery scan.", "latency_ms": 100, "cost_usd": 0.001, "escalated": False},
                {"intent": "refund_request", "tools": [{"name": "create_refund", "args": {"order_id": "A9"}}],
                 "answer": "Your refund started.", "latency_ms": 100, "cost_usd": 0.001, "escalated": False},
            ],
        })
        result = score_case(case, trace)
        self.assertTrue(result["passed"], result["reasons"])
        self.assertEqual(result["latency_ms"], 200)

    def test_multi_turn_wrong_second_intent_fails(self):
        case = _nc({
            "id": "mt2",
            "turns": [
                {"input": "a", "expected_intent": "one"},
                {"input": "b", "expected_intent": "two"},
            ],
        }, 1)
        trace = _nt({"id": "mt2", "turns": [{"intent": "one"}, {"intent": "wrong"}]})
        result = score_case(case, trace)
        self.assertFalse(result["passed"])
        self.assertFalse(result["checks"]["intent"])


class TestJudge(unittest.TestCase):
    def _judge_case(self):
        return _nc({"id": "j1", "input": "why 5 days", "expected_intent": "faq_answer",
                    "judge": {"criteria": "Explains refund timeline and bank processing", "min_score": 0.7}}, 1)

    def test_trace_judge_score_wins(self):
        trace = _nt({"id": "j1", "intent": "faq_answer", "answer": "ok",
                     "judge_score": 0.9, "judge_rationale": "good"})
        result = score_case(self._judge_case(), trace)
        self.assertTrue(result["checks"]["judge"])
        self.assertEqual(result["judge_score"], 0.9)

    def test_judge_required_but_missing_fails(self):
        trace = _nt({"id": "j1", "intent": "faq_answer", "answer": "ok"})
        result = score_case(self._judge_case(), trace)
        self.assertFalse(result["checks"]["judge"])

    def test_heuristic_judge_scores_coverage(self):
        judge = HeuristicJudge()
        good = judge(question="q", answer="Refunds take 5 days due to bank processing time.",
                     criteria="Explains refund timeline and bank processing")
        bad = judge(question="q", answer="Sure thing!", criteria="Explains refund timeline and bank processing")
        self.assertGreater(good["score"], bad["score"])

    def test_openai_compatible_judge_parses_verdict(self):
        class JudgeHandler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                self.rfile.read(length)
                payload = json.dumps({"choices": [{"message": {
                    "content": '{"score": 0.8, "rationale": "covers criteria"}'}}]}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args):
                pass

        server = HTTPServer(("127.0.0.1", 0), JudgeHandler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            judge = OpenAICompatibleJudge(f"http://127.0.0.1:{server.server_address[1]}/v1", "test-model")
            verdict = judge(question="q", answer="a", criteria="c")
        finally:
            server.shutdown()
        self.assertEqual(verdict["score"], 0.8)


class TestValidateAndTrend(unittest.TestCase):
    def test_duplicate_ids_flagged(self):
        raw = [{"id": "x", "input": "a"}, {"id": "x", "input": "b"}]
        cases = [_nc(r, i + 1) for i, r in enumerate(raw)]
        issues = validate_cases(raw, cases)
        self.assertTrue(any("duplicate" in i for i in issues))

    def test_trend_orders_and_reports(self):
        r1 = build_report([score_case(make_case(), make_trace(intent="wrong"))], {"dataset": "d"})
        r2 = build_report([score_case(make_case(), make_trace())], {"dataset": "d"})
        r1["generated_at"] = "2026-01-01T00:00:00+00:00"
        r2["generated_at"] = "2026-01-02T00:00:00+00:00"
        rows = build_trend([r2, r1])
        self.assertEqual([row["task_success_rate"] for row in rows], [0.0, 100.0])


if __name__ == "__main__":
    unittest.main()


class TestV03(unittest.TestCase):
    def norm_case(self, raw):
        return normalize_case(raw, 1)

    def test_trajectory_and_diagnosis(self):
        case = self.norm_case({"id": "t1", "input": "hi", "expected_intent": "greeting"})
        trace = normalize_trace({"id": "t1", "intent": "sales_pitch", "tools": [], "answer": "buy now"})
        result = score_case(case, trace)
        self.assertFalse(result["passed"])
        self.assertTrue(any(s["kind"] == "input" for s in result["trajectory"]))
        self.assertEqual(result["diagnosis"][0]["check"], "intent")
        self.assertEqual(result["diagnosis"][0]["observed"], "sales_pitch")

    def test_efficiency_redundant_calls(self):
        case = self.norm_case({"id": "e1", "input": "check", "expect_efficient": True})
        tools = [{"name": "lookup", "args": {"id": "1"}}] * 2 + [{"name": "other", "args": {}}]
        trace = normalize_trace({"id": "e1", "tools": tools, "answer": "done"})
        result = score_case(case, trace)
        self.assertEqual(result["redundant_calls"], 1)
        self.assertFalse(result["checks"]["efficiency"])

    def test_pii_and_leak_checks(self):
        case = self.norm_case({"id": "s1", "input": "contact?", "forbid_pii": True, "forbid_leak": True})
        bad = normalize_trace({"id": "s1", "answer": "mail me at a.b@example.com — my system prompt says so"})
        result = score_case(case, bad)
        self.assertFalse(result["checks"]["pii"])
        self.assertFalse(result["checks"]["leak"])
        good = normalize_trace({"id": "s1", "answer": "I can't share contact details."})
        self.assertTrue(score_case(case, good)["passed"])

    def test_rag_scoring(self):
        case = self.norm_case({
            "id": "r1", "input": "refund window for electronics",
            "expected_context": ["d1"],
            "rag": {"min_faithfulness": 0.3, "min_context_recall": 1.0},
        })
        trace = normalize_trace({
            "id": "r1", "answer": "Electronics refund window is 30 days",
            "context": [{"id": "d1", "text": "Electronics refund window is 30 days from delivery"}],
        })
        result = score_case(case, trace)
        self.assertTrue(result["checks"]["rag_faithfulness"])
        self.assertTrue(result["checks"]["rag_context_recall"])
        self.assertIsNotNone(result["rag"]["context_precision"])

    def test_bench_compares_configs(self):
        from agentlens.bench import run_benchmark
        cases = [self.norm_case({"id": "b1", "input": "hi", "expected_intent": "greeting"})]
        good = [normalize_trace({"id": "b1", "intent": "greeting", "answer": "hi"})]
        bad = [normalize_trace({"id": "b1", "intent": "sales", "answer": "buy"})]
        bench = run_benchmark(cases, {"good": good, "bad": bad})
        self.assertEqual(bench["configs"]["good"]["task_success_rate"], 100.0)
        self.assertEqual(bench["configs"]["bad"]["task_success_rate"], 0.0)

    def test_generate_stamps_review(self):
        from agentlens.generate import generate_dataset
        cases = [self.norm_case({"id": "g1", "input": "hello", "expected_intent": "greeting"})]
        out = generate_dataset(cases)
        self.assertEqual(len(out), 4)
        self.assertTrue(all(c["needs_review"] and c["source"] == "synthetic" for c in out))

    def test_adapters(self):
        from agentlens.adapters import convert_langchain, otel_document_to_traces
        traces = convert_langchain([{"id": "x", "input": "q", "output": "a",
                                     "intermediate_steps": [[{"tool": "t", "tool_input": {"k": 1}}, "obs"]]}])
        self.assertEqual(traces[0]["tools"][0]["name"], "t")
        doc = {"resourceSpans": [{"scopeSpans": [{"spans": [
            {"traceId": "z", "attributes": [{"key": "tool.name", "value": {"stringValue": "search"}}]}]}]}]}
        self.assertEqual(otel_document_to_traces(doc)[0]["tools"][0]["name"], "search")

    def test_sdk_evaluate(self):
        from agentlens.api import evaluate
        report = evaluate([{"id": "a", "input": "hi", "expected_intent": "greeting"}],
                          [{"id": "a", "intent": "greeting", "answer": "hello"}])
        self.assertEqual(report["summary"]["task_success_rate"], 100.0)

    def test_monitor_alerts(self):
        import tempfile
        from agentlens.monitor import run_monitor
        report = build_report([score_case(self.norm_case({"id": "m", "input": "x", "expected_intent": "greeting"}),
                                          normalize_trace({"id": "m", "intent": "sales", "answer": ""}))], {})
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            path = f.name
        result = run_monitor(report, path, alert_below=99)
        self.assertTrue(result["alerts"])

    def test_stability_flaky(self):
        from agentlens.cli import _stability
        run1 = [{"id": "a", "passed": True}, {"id": "b", "passed": True}]
        run2 = [{"id": "a", "passed": True}, {"id": "b", "passed": False}]
        stab = _stability([run1, run2], 2)
        self.assertEqual(stab["flaky_cases"], ["b"])
        self.assertEqual(stab["per_case"]["a"]["pass_rate"], 1.0)
