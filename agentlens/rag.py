"""Lightweight, deterministic RAG evaluation.

These are transparent heuristic metrics, not model-based judgments:

- **faithfulness** — share of the answer's content words that are
  supported by the retrieved context (a proxy; a high score does not
  prove the answer is true, a low score flags unsupported content),
- **answer relevancy** — overlap between the answer and the question,
- **context recall** — share of the case's expected context ids that
  the agent actually retrieved,
- **context precision** — share of retrieved contexts that were
  expected/relevant.

A trace carries retrieval results as ``context``: a list of strings or
``{"id": ..., "text": ...}`` objects. A case declares expectations in a
``rag`` block and, optionally, ``expected_context`` ids.
"""
from __future__ import annotations

import re

_STOP = {
    "the", "a", "an", "is", "are", "was", "were", "of", "to", "in", "on",
    "for", "and", "or", "it", "this", "that", "with", "as", "by", "at",
    "from", "be", "has", "have", "had", "you", "your", "we", "our",
}


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", (text or "").lower()) if w not in _STOP and len(w) > 2}


def _context_items(trace: dict) -> list[dict]:
    items = []
    for i, entry in enumerate(trace.get("context") or []):
        if isinstance(entry, str):
            items.append({"id": f"ctx-{i + 1}", "text": entry})
        elif isinstance(entry, dict):
            items.append({"id": str(entry.get("id") or f"ctx-{i + 1}"),
                          "text": entry.get("text") or entry.get("content") or ""})
    return items


def rag_scores(case: dict, trace: dict) -> dict | None:
    """Return the RAG metric dict, or None when the case has no rag block."""
    cfg = case.get("rag")
    if not cfg:
        return None
    items = _context_items(trace)
    context_words: set[str] = set()
    for item in items:
        context_words |= _words(item["text"])
    answer_words = _words(trace.get("answer") or "")
    question_words = _words(case["input"])

    faithfulness = None
    if answer_words:
        faithfulness = round(len(answer_words & context_words) / len(answer_words), 4) if context_words else 0.0
    relevancy = None
    if answer_words and question_words:
        relevancy = round(len(answer_words & question_words) / len(question_words), 4)

    expected_ids = [str(x) for x in (case.get("expected_context") or [])]
    retrieved_ids = [item["id"] for item in items]
    recall = precision = None
    if expected_ids:
        recall = round(len(set(expected_ids) & set(retrieved_ids)) / len(expected_ids), 4)
        if retrieved_ids:
            precision = round(len(set(expected_ids) & set(retrieved_ids)) / len(retrieved_ids), 4)

    return {
        "faithfulness": faithfulness,
        "relevancy": relevancy,
        "context_recall": recall,
        "context_precision": precision,
        "retrieved": retrieved_ids,
    }
