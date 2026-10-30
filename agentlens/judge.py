"""LLM-as-judge scoring for open-ended answers.

A case opts in with::

    "judge": {"criteria": "Explains the refund timeline and mentions bank
              processing time", "min_score": 0.7}

Two judges are provided:

- ``HeuristicJudge`` — offline, deterministic. Scores how much of the
  criteria's content vocabulary the answer actually covers. Crude, but
  useful as a smoke signal with zero setup. Treat it as a fallback, not
  a replacement for a real model judge.
- ``OpenAICompatibleJudge`` — calls any OpenAI-compatible chat-completions
  endpoint (OpenAI, or a local server such as Ollama/LM Studio via its
  OpenAI-compatible API) and parses a JSON verdict.

A recorded trace may also carry ``judge_score`` directly; that always
wins, so historical runs stay reproducible without re-calling a model.
Human spot-checks remain essential: judge scores drift, so review a
sample of judged cases by hand, especially after changing judge models.
"""
from __future__ import annotations

import json
import os
import re
import urllib.request

_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "is", "are", "it",
    "that", "this", "with", "for", "on", "as", "be", "by", "at", "from",
    "should", "must", "answer", "response", "mentions", "mention",
    "explains", "explain", "includes", "include", "user", "agent",
}


JUDGE_PROMPT_VERSION = "1"


def _content_words(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    return {w for w in words if len(w) > 2 and w not in _STOPWORDS}


class HeuristicJudge:
    name = "heuristic"

    def __call__(self, *, question: str, answer: str, criteria: str) -> dict:
        wanted = _content_words(criteria)
        if not wanted:
            return {"score": 0.0, "rationale": "judge criteria had no content words"}
        present = _content_words(answer)
        hits = wanted & present
        score = round(len(hits) / len(wanted), 4)
        missing = sorted(wanted - present)
        rationale = f"covered {len(hits)}/{len(wanted)} criteria concepts"
        if missing:
            rationale += f"; missing: {', '.join(missing[:6])}"
        return {"score": score, "rationale": rationale}


class OpenAICompatibleJudge:
    """Judge via an OpenAI-compatible /chat/completions endpoint."""

    name = "openai-compatible"

    def __init__(self, endpoint: str, model: str, api_key: str | None = None, timeout: int = 60):
        self.endpoint = endpoint.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = timeout

    def __call__(self, *, question: str, answer: str, criteria: str) -> dict:
        prompt = (
            "You are an impartial evaluator. Score the agent's answer from 0 to 1 "
            "against the criteria. Reply with ONLY a JSON object like "
            '{"score": 0.8, "rationale": "short reason"}.\n\n'
            f"User question: {question}\n\nAgent answer: {answer}\n\nCriteria: {criteria}"
        )
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
        }
        req = urllib.request.Request(
            f"{self.endpoint}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        if self.api_key:
            req.add_header("Authorization", f"Bearer {self.api_key}")
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        content = data["choices"][0]["message"]["content"]
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if not match:
            raise ValueError(f"judge did not return JSON: {content[:200]}")
        verdict = json.loads(match.group(0))
        return {
            "score": max(0.0, min(1.0, float(verdict["score"]))),
            "rationale": str(verdict.get("rationale", ""))[:500],
        }


def build_judge(kind: str, *, endpoint: str | None = None, model: str | None = None,
                api_key_env: str = "JUDGE_API_KEY"):
    """Construct a judge from CLI options. ``kind``: none|heuristic|openai."""
    if kind in (None, "none"):
        return None
    if kind == "heuristic":
        return HeuristicJudge()
    if kind == "openai":
        if not endpoint or not model:
            raise SystemExit("--judge openai requires --judge-endpoint and --judge-model")
        return OpenAICompatibleJudge(endpoint, model, api_key=os.environ.get(api_key_env))
    raise SystemExit(f"unknown judge kind: {kind}")
