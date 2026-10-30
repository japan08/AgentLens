"""A tiny dependency-free HTTP API for AgentLens.

    python -m agentlens serve --port 8765

- ``GET  /health``   → ``{"ok": true}``
- ``POST /evaluate`` → body ``{"cases": [...], "traces": [...]}``
  (the raw JSONL object formats) and returns the full report JSON.

Local development use: it binds to localhost by default and performs
no authentication.
"""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer

from .api import evaluate


def make_handler():
    class Handler(BaseHTTPRequestHandler):
        def _send(self, code, payload):
            body = json.dumps(payload).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):  # noqa: N802 (stdlib naming)
            if self.path == "/health":
                self._send(200, {"ok": True})
            else:
                self._send(404, {"error": "not found"})

        def do_POST(self):  # noqa: N802
            if self.path != "/evaluate":
                self._send(404, {"error": "not found"})
                return
            try:
                length = int(self.headers.get("Content-Length") or 0)
                payload = json.loads(self.rfile.read(length) or b"{}")
                report = evaluate(payload.get("cases") or [], payload.get("traces") or [])
                self._send(200, report)
            except Exception as e:  # surface the error, never crash the server
                self._send(400, {"error": str(e)})

        def log_message(self, *args):  # keep stdout clean
            pass

    return Handler


def serve(host: str = "127.0.0.1", port: int = 8765) -> None:
    server = HTTPServer((host, port), make_handler())
    print(f"AgentLens API listening on http://{host}:{port} (POST /evaluate, GET /health)")
    server.serve_forever()
