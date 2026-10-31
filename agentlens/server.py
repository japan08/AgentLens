"""A tiny dependency-free HTTP API for AgentLens.

    python -m agentlens serve --port 8765

- ``GET  /health``   → ``{"ok": true}``
- ``POST /evaluate`` → body ``{"cases": [...], "traces": [...]}``
  (the raw JSONL object formats) and returns the full report JSON.

Hardening (v0.4):

- **Authentication**: when the ``AGENTLENS_API_TOKEN`` environment
  variable is set, ``/evaluate`` requires
  ``Authorization: Bearer <token>``. ``/health`` stays open so load
  balancers can probe it. With no token set the server behaves as
  before — local development only.
- **Request limit**: bodies over 5 MB are rejected with ``413``.
- **Error envelope**: every error is
  ``{"error": {"code": ..., "message": ...}}`` with a matching HTTP
  status (400 invalid input, 401 unauthorized, 404 unknown route,
  405 wrong method, 413 too large).

It binds to localhost by default. Do not expose it to a network
without the token set (and ideally a reverse proxy with TLS).
"""
from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

from .api import evaluate

MAX_BODY_BYTES = 5_000_000


def _error(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}}


def make_handler(token: str | None = None):
    expected = token if token is not None else os.environ.get("AGENTLENS_API_TOKEN") or None

    class Handler(BaseHTTPRequestHandler):
        def _send(self, code, payload):
            body = json.dumps(payload).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _authorized(self) -> bool:
            if expected is None:
                return True
            return self.headers.get("Authorization") == f"Bearer {expected}"

        def do_GET(self):  # noqa: N802 (stdlib naming)
            if self.path == "/health":
                self._send(200, {"ok": True})
            elif self.path == "/evaluate":
                self._send(405, _error("method_not_allowed", "use POST /evaluate"))
            else:
                self._send(404, _error("not_found", "unknown route"))

        def do_POST(self):  # noqa: N802
            if self.path != "/evaluate":
                self._send(404, _error("not_found", "unknown route"))
                return
            if not self._authorized():
                self._send(401, _error("unauthorized", "missing or invalid bearer token"))
                return
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                self._send(400, _error("invalid_request", "bad Content-Length"))
                return
            if length > MAX_BODY_BYTES:
                self._send(413, _error("payload_too_large", f"body exceeds {MAX_BODY_BYTES} bytes"))
                return
            raw = self.rfile.read(length) if length else b"{}"
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                self._send(400, _error("invalid_json", "request body is not valid JSON"))
                return
            if not isinstance(payload, dict):
                self._send(400, _error("invalid_request", "body must be a JSON object"))
                return
            try:
                report = evaluate(payload.get("cases") or [], payload.get("traces") or [])
            except Exception as e:  # surface the error, never crash the server
                self._send(400, _error("evaluation_failed", str(e)))
                return
            self._send(200, report)

        def log_message(self, *args):  # keep stdout clean
            pass

    return Handler


def serve(host: str = "127.0.0.1", port: int = 8765) -> None:
    token = os.environ.get("AGENTLENS_API_TOKEN") or None
    server = HTTPServer((host, port), make_handler(token))
    auth = "token auth ON" if token else "no token set (local development only)"
    print(f"AgentLens API listening on http://{host}:{port} (POST /evaluate, GET /health; {auth})")
    server.serve_forever()
