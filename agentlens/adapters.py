"""Convert foreign trace formats into AgentLens traces.

These are *format converters*, tested against the documented shapes
below — not live integrations with any framework. Anything that can
emit one of these shapes (or the native AgentLens JSONL) can be
evaluated.

- **LangChain-style run records**: objects with ``input``, ``output``,
  ``intermediate_steps`` (``[action, observation]`` pairs where the
  action has ``tool`` and ``tool_input``), optional ``latency_ms`` /
  ``cost_usd`` / ``escalated``.
- **OpenTelemetry spans (OTLP JSON)**: spans grouped by trace id; tool
  spans carry a ``tool.name`` (or ``gen_ai.tool.name``) attribute and
  JSON ``tool.args``; the root span may carry ``agent.input`` /
  ``agent.answer`` / ``agent.intent`` attributes.
- **LlamaIndex-style records**: objects with ``query`` (or ``input``),
  ``response`` (or ``output``) and ``tool_calls`` / ``sources`` — the
  shape a query-engine or agent handler naturally logs.
- **MCP tools**: no conversion needed — MCP tool names are ordinary
  tool names in an AgentLens trace (see ``examples/mcp_cases.jsonl``).
"""
from __future__ import annotations

import json


def langchain_record_to_trace(record: dict) -> dict:
    tools = []
    for step in record.get("intermediate_steps") or []:
        action = step[0] if isinstance(step, (list, tuple)) and step else step
        if isinstance(action, dict):
            tools.append({"name": action.get("tool", ""), "args": action.get("tool_input") or {}})
    for call in record.get("tool_calls") or []:
        tools.append({"name": call.get("name", ""), "args": call.get("args") or {}})
    return {
        "id": record.get("id"),
        "input": record.get("input") or record.get("question") or "",
        "intent": record.get("intent"),
        "flow": record.get("flow"),
        "tools": tools,
        "answer": record.get("output") or record.get("answer") or "",
        "latency_ms": record.get("latency_ms"),
        "cost_usd": record.get("cost_usd"),
        "escalated": record.get("escalated"),
        "context": record.get("context"),
    }


def convert_langchain(records: list[dict]) -> list[dict]:
    return [langchain_record_to_trace(r) for r in records]


def _span_attrs(span: dict) -> dict:
    attrs = {}
    for kv in span.get("attributes") or []:
        key = kv.get("key", "")
        value = kv.get("value") or {}
        attrs[key] = next((v for v in value.values() if v is not None), None)
    return attrs


def otel_document_to_traces(doc: dict) -> list[dict]:
    traces: dict[str, dict] = {}
    order: list[str] = []
    for resource in doc.get("resourceSpans") or []:
        for scope in resource.get("scopeSpans") or []:
            for span in scope.get("spans") or []:
                trace_id = span.get("traceId") or "trace"
                if trace_id not in traces:
                    traces[trace_id] = {
                        "id": trace_id, "input": "", "intent": None, "flow": None,
                        "tools": [], "answer": "", "latency_ms": None,
                        "cost_usd": None, "escalated": None, "context": None,
                    }
                    order.append(trace_id)
                trace = traces[trace_id]
                attrs = _span_attrs(span)
                tool_name = attrs.get("tool.name") or attrs.get("gen_ai.tool.name")
                if tool_name:
                    args = attrs.get("tool.args") or {}
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except json.JSONDecodeError:
                            args = {"_raw": args}
                    trace["tools"].append({"name": str(tool_name), "args": args})
                if attrs.get("agent.input"):
                    trace["input"] = str(attrs["agent.input"])
                if attrs.get("agent.answer"):
                    trace["answer"] = str(attrs["agent.answer"])
                if attrs.get("agent.intent"):
                    trace["intent"] = str(attrs["agent.intent"])
                start = int(span.get("startTimeUnixNano") or 0)
                end = int(span.get("endTimeUnixNano") or 0)
                if start and end:
                    duration_ms = round((end - start) / 1e6, 1)
                    trace["latency_ms"] = max(trace["latency_ms"] or 0, duration_ms)
    return [traces[t] for t in order]


def llamaindex_record_to_trace(record: dict) -> dict:
    """Convert one LlamaIndex-style record (query/response/tool_calls)."""
    tools = []
    for call in record.get("tool_calls") or []:
        if isinstance(call, dict):
            tools.append({"name": call.get("name") or call.get("tool") or "",
                          "args": call.get("args") or call.get("tool_kwargs") or {}})
    context = None
    sources = record.get("sources") or record.get("source_nodes")
    if sources:
        texts = []
        for node in sources:
            if isinstance(node, dict):
                texts.append(str(node.get("text") or node.get("content") or ""))
            else:
                texts.append(str(node))
        context = [x for x in texts if x] or None
    return {
        "id": record.get("id"),
        "input": record.get("query") or record.get("input") or "",
        "intent": record.get("intent"),
        "flow": record.get("flow"),
        "tools": tools,
        "answer": record.get("response") or record.get("output") or record.get("answer") or "",
        "latency_ms": record.get("latency_ms"),
        "cost_usd": record.get("cost_usd"),
        "escalated": record.get("escalated"),
        "context": context if context is not None else record.get("context"),
    }


def convert_llamaindex(records: list[dict]) -> list[dict]:
    return [llamaindex_record_to_trace(r) for r in records]
