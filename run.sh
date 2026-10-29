#!/usr/bin/env bash
# AgentLens convenience runner script
set -e

PORT=${PORT:-8080}
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "=== AgentLens: Running Backend Evaluation ==="
python3 -m agentlens demo

echo ""
echo "=== AgentLens: Starting Frontend Dashboard ==="
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null ; then
    echo "Frontend server is already running on port $PORT."
else
    echo "Starting HTTP server on http://localhost:$PORT..."
    python3 -m http.server $PORT &
    SERVER_PID=$!
    echo "Server started with PID: $SERVER_PID"
fi

echo ""
echo "=== Access AgentLens ==="
echo "  Dashboard:   http://localhost:$PORT/"
echo "  Demo Report: http://localhost:$PORT/reports/demo/report.html"
echo ""
