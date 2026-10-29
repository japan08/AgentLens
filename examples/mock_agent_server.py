"""A lightweight mock agent HTTP server for testing live agent evaluation.

Accepts POST requests at /eval with {"id": "...", "input": "..."} and returns
realistic agent execution traces in the AgentLens format.

Usage:
    python3 examples/mock_agent_server.py [--port 9000]

Test with AgentLens:
    python3 -m agentlens run --cases examples/cases.jsonl --endpoint http://localhost:9000/eval --out reports/live_demo
"""
import argparse
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRACES_PATH = ROOT / "examples" / "traces.sample.jsonl"


def load_sample_traces():
    traces = {}
    if TRACES_PATH.exists():
        with open(TRACES_PATH, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    trace = json.loads(line)
                    if "id" in trace:
                        traces[trace["id"]] = trace
    return traces


SAMPLE_TRACES = load_sample_traces()


class AgentHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        post_body = self.rfile.read(content_length) if content_length > 0 else b"{}"
        try:
            req = json.loads(post_body.decode("utf-8"))
        except Exception:
            req = {}

        case_id = req.get("id", "unknown")
        user_input = req.get("input", "")

        # Use recorded sample trace if known, otherwise mock response
        if case_id in SAMPLE_TRACES:
            trace = dict(SAMPLE_TRACES[case_id])
        else:
            trace = {
                "id": case_id,
                "input": user_input,
                "intent": "general_inquiry",
                "tools": [],
                "answer": f"Mock agent received: {user_input}",
                "latency_ms": 120,
                "cost_usd": 0.0005,
                "escalated": False,
            }

        response_bytes = json.dumps(trace).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response_bytes)))
        self.end_headers()
        self.wfile.write(response_bytes)

    def log_message(self, format, *args):
        # Concise logging
        print(f"[MockAgent] {self.address_string()} - {format % args}")


def main():
    parser = argparse.ArgumentParser(description="Run mock agent HTTP endpoint for AgentLens")
    parser.add_argument("--port", type=int, default=9000, help="Port to listen on (default: 9000)")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface (default: 127.0.0.1)")
    args = parser.parse_args()

    server = HTTPServer((args.host, args.port), AgentHandler)
    print(f"Mock Agent HTTP Server listening on http://{args.host}:{args.port}/eval")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server.")
        server.server_close()


if __name__ == "__main__":
    main()
