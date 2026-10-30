# Contributing to AgentLens

Thanks for helping improve AgentLens. The bar is simple: the core stays
dependency-free, deterministic and honest about what its metrics mean.

## Setup

```bash
git clone https://github.com/japan08/AgentLens
cd AgentLens
python -m unittest discover -s tests   # no dependencies to install
python -m agentlens demo
```

## Ground rules

- **Standard library only** in the `agentlens` package. Optional
  integrations belong in converters (`adapters.py`) or external tools.
- **Every new check needs**: an entry in `CHECK_KEYS`, a diagnosis hint,
  unit tests for pass and fail, and a definition in `METRICS.md`.
- **Deterministic tests.** No network, no real model calls in unit
  tests; fake judges and stub HTTP servers are already used in the
  suite — follow those patterns.
- **Documentation examples must run.** If you change a CLI command,
  update the README/docs examples and run them once yourself.
- **No overclaiming.** Do not document framework support, benchmark
  numbers or production readiness that is not implemented, tested and
  reproducible from this repository.

## Workflow

1. Fork and branch from `main`.
2. Make the change with tests.
3. Run the full suite plus the demo and the example datasets
   (see `BENCHMARKS.md` for the commands).
4. Open a pull request describing the behaviour change and its tests.
