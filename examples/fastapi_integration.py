"""Minimal FastAPI integration example for AgentLens.

This is an *example*, not a bundled dependency: AgentLens itself stays
dependency-free. Install FastAPI in your own service
(``pip install fastapi uvicorn``), run your agent as usual, log one
trace dict per request, and evaluate batches with the AgentLens SDK.

Run:
    uvicorn examples.fastapi_integration:app --port 9000

Then:
    curl -X POST localhost:9000/agent -d '{"message": "Where is order 42?"}'
    curl localhost:9000/evaluate        # scores everything logged so far

The trace dict shape below is the native AgentLens trace format, so
no conversion is needed. For LangChain/LlamaIndex/OpenTelemetry
shapes, see ``agentlens convert``.
"""
from __future__ import annotations

try:
    from fastapi import FastAPI
except ImportError as e:  # pragma: no cover - example guard
    raise SystemExit("This example needs FastAPI: pip install fastapi uvicorn") from e

from agentlens import evaluate

app = FastAPI(title="AgentLens FastAPI example")

# In a real service this would be your agent under test.
TRACES: list[dict] = []


def my_agent(message: str) -> dict:
    """Replace with your real agent call; return an AgentLens trace."""
    return {
        "input": message,
        "intent": "order_status",
        "tools": [{"name": "track_order", "args": {"order_id": "42"}}],
        "answer": "Order 42 is in transit.",
        "latency_ms": 120,
        "cost_usd": 0.001,
        "escalated": False,
    }


@app.post("/agent")
def run_agent(payload: dict) -> dict:
    trace = my_agent(str(payload.get("message", "")))
    TRACES.append(trace)
    return {"answer": trace["answer"]}


@app.get("/evaluate")
def evaluate_logged() -> dict:
    cases = [
        {"id": "order-status", "input": "Where is order 42?",
         "expect_intent": "order_status",
         "expect_tools": [{"name": "track_order", "args": {"order_id": "42"}}],
         "answer_must_include": ["in transit"]},
    ]
    report = evaluate(cases, TRACES)
    return {"summary": report["summary"], "security_findings": report["security_findings"]}
