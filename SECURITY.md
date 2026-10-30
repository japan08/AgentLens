# Security

## Reporting a vulnerability

Open a GitHub issue marked `security` in the AgentLens repository, or
contact the maintainer through the repository owner's GitHub profile.
Please do not include real credentials, live tokens or personal data in
reports.

## Security model and boundaries

- **Traces can contain sensitive data.** AgentLens evaluates recorded
  agent behaviour; tool arguments and answers may contain personal or
  business data. Treat trace and report files as sensitive: store them
  with the same care as logs, and review before sharing publicly.
- **Safety findings are redacted by design.** PII/leak findings record
  the pattern type (for example `email`, `card_number`), never the
  matched value, so reports are safer to share than raw traces.
- **The HTTP API is a local development tool.** `agentlens serve` binds
  to `127.0.0.1` by default and performs no authentication. Do not
  expose it to a network without your own authenticated reverse proxy.
- **The live runner posts case inputs to the endpoint you give it.**
  Only point `--endpoint` at agents you control or are authorized to
  test; case inputs are sent verbatim.
- **Judge endpoints receive questions, answers and criteria.** When
  using `--judge openai`, that content is sent to the endpoint you
  configure. Use an endpoint whose data handling you accept.
- **Synthetic cases are untrusted input.** `agentlens generate` output
  is stamped `needs_review`; review expectations before using generated
  cases to gate anything.

## What AgentLens checks (and what it does not)

The security suite checks observable behaviour: forbidden tool calls,
PII patterns and system-prompt-leak markers in answers, and escalation
expectations. It is a regression tripwire for known failure modes — not
a guarantee that an agent is secure, and not a substitute for dedicated
red-teaming of a production system.
