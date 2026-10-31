"""Continuous evaluation bookkeeping.

Each monitor run appends one summary line to a history JSONL file and
compares it with the previous run: it alerts (exit code 2) when the
task success rate falls below ``--alert-below`` percent or drops more
than ``--max-drop`` points versus the previous recorded run. Wire it
into cron or CI for scheduled/production-sample evaluation.
"""
from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def read_history(path) -> list[dict]:
    path = Path(path)
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def run_monitor(report: dict, history_path, *, alert_below: float | None = None,
                max_drop: float | None = None) -> dict:
    summary = report["summary"]
    previous = read_history(history_path)
    last = previous[-1] if previous else None
    entry = {
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "task_success_rate": summary["task_success_rate"],
        "passed": summary["passed"],
        "total_cases": summary["total_cases"],
        "safety_violations": summary.get("safety_violations"),
    }
    alerts = []
    if alert_below is not None and entry["task_success_rate"] < alert_below:
        alerts.append(f"task success {entry['task_success_rate']}% is below the alert threshold {alert_below}%")
    if last is not None and max_drop is not None:
        drop = round(last["task_success_rate"] - entry["task_success_rate"], 2)
        if drop > max_drop:
            alerts.append(f"task success dropped {drop} points since the previous run "
                          f"({last['task_success_rate']}% → {entry['task_success_rate']}%)")
    with open(history_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    return {"entry": entry, "previous": last, "alerts": alerts}


def post_webhook(url: str, payload: dict, timeout: float = 5.0) -> bool:
    """POST a JSON payload to a webhook URL. Returns True on a 2xx.

    Used for monitor alerts. Failures return False (and the caller
    warns) — a dead webhook must never mask the alert itself or crash
    the monitor run.
    """
    try:
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return 200 <= response.status < 300
    except Exception:
        return False
