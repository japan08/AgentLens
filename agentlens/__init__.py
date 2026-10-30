"""AgentLens — a small, dependency-free evaluation harness for AI agents.

Scores an agent on *task success*, not just answer quality: intent/routing,
tool-call trajectory (right tool, right arguments, right order), forbidden
actions, safety, escalation behaviour, latency and cost per successful task.

Programmatic use::

    from agentlens import evaluate
    report = evaluate(cases, traces)
"""

__version__ = "0.3.0"

from .api import evaluate  # noqa: E402

__all__ = ["evaluate", "__version__"]
