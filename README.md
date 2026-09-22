# Dynamic-Tariff Home Energy Scheduling Optimizer

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Schedules shiftable household appliance runs (dishwasher, washing machine, EV charging)
against real day-ahead electricity prices from [aWATTar](https://www.awattar.de/) to
minimize cost, and quantifies the savings versus running appliances at a fixed,
"whenever convenient" time.

> **Project status:** solo-maintained portfolio project, structured like a real
> open-source project (see [`CONTRIBUTING.md`](CONTRIBUTING.md#project-status) for what
> that does and doesn't mean in practice).

## Table of contents

- [What this does](#what-this-does)
- [Architecture](#architecture)
- [The scheduling problem](#the-scheduling-problem)
- [Failure handling](#failure-handling)
- [Getting started](#getting-started)
- [Tests](#tests)
- [Documentation](#documentation)
- [Known limitations](#known-limitations--must-build-vs-nice-to-have)
- [Contributing](#contributing)
- [License](#license)

## What this does

You tell it which appliances you need to run, how long each takes, how much power they
draw, and the time window each one is allowed to run in (e.g., "dishwasher, 2 hours,
1.5 kW, sometime in the next 24 hours"). It fetches real day-ahead hourly electricity
prices and computes:

1. A **naive baseline** schedule — what running appliances at a fixed, habitual time would
   cost, as a fair comparison point (not a strawman; see
   [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md#why-three-schedules-are-computed-on-every-apischedule-call-not-just-the-best-one)).
2. A **single-load optimal** schedule — each appliance's individually cheapest window,
   ignoring interactions with other appliances.
3. The **fully optimized** schedule — the cheapest arrangement of *all* appliances
   simultaneously, respecting a shared household power-capacity limit (you can't run the
   dishwasher and the EV charger at once if that would trip the breaker).

The frontend shows the price curve with schedule overlays, a per-appliance timeline
comparing naive vs. optimized placement, a savings summary, and a per-hour capacity-usage
chart that makes the shared-capacity constraint visibly checkable rather than just
backend-asserted.

## Architecture

```
backend/    FastAPI service: aWATTar price fetch + cache, scheduling engine, REST API
frontend/   React + TypeScript UI: live price chart, appliance config, schedule/savings view
analysis/   Standalone script validating the scheduler against a PuLP MILP true optimum
docs/       Architecture rationale, API reference, development guide
```

For the full picture — component responsibilities, data flow through a single request, and
the reasoning behind non-obvious design choices — see
**[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)**.

## The scheduling problem

- **Single load:** cheapest contiguous window of a fixed duration within an allowed
  window — a sliding-window minimum, O(hours) per load.
- **Multiple loads sharing one household power limit (the real engineering core):**
  a load's individually cheapest window can collide with another load's cheapest window
  on the same circuit, so placements interact — this is not "sort by cheapest hour."
  Implemented as an exact branch-and-bound backtracking search (most-constrained-load-first
  ordering, cheapest-candidate-first branching, pruned the moment a partial cost can no
  longer beat the best complete solution found). See
  [`backend/app/scheduler.py`](backend/app/scheduler.py) for the full design rationale in
  the docstring, and
  [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md#why-the-multi-load-scheduler-is-a-hand-written-backtracking-search-instead-of-calling-a-solver-directly-in-the-request-path)
  for why this approach over calling a solver directly.
- **Validation:** [`analysis/validate_optimum.py`](analysis/validate_optimum.py) formulates
  the identical problem as a MILP (binary start-time indicators, a capacity constraint per
  hour) and solves it with PuLP/CBC, then compares against the backtracking search's answer
  across randomly generated scenarios. Across 150 generated scenarios (11 infeasible under
  both methods, excluded from cost comparison), the backtracking search matched the true
  optimum with **zero mismatches and zero optimality gap**, running in ~0.1ms median per
  scenario — confirming the search is genuinely exact at household scale, not a heuristic
  with lucky results. Reproduce with:
  ```bash
  pip install -r backend/requirements.txt
  python analysis/validate_optimum.py --scenarios 200
  ```

## Failure handling

- aWATTar unreachable → serve the last cached prices with an `is_stale` flag rather than
  crash; refuse to serve anything older than 48h (stale data past that point would be
  actively misleading, not just imprecise). See
  [`backend/app/price_fetcher.py`](backend/app/price_fetcher.py).
- A load whose deadline is infeasible given its duration/window, or that cannot be placed
  under the shared capacity constraint at all → reported explicitly via
  `infeasible_load_ids`, never silently dropped or overcommitted.

Full table of failure modes and behavior:
[`docs/ARCHITECTURE.md#failure-handling-philosophy`](docs/ARCHITECTURE.md#failure-handling-philosophy).

## Getting started

```bash
git clone git@github.com:jamnxdev/energy-optimizer.git
cd energy-optimizer
docker compose up --build
```

- Backend: http://localhost:8000 (`/api/health`, `/api/prices`, `/api/schedule`)
- Frontend: http://localhost:5173

For configuration (env vars), running without Docker, troubleshooting, and common
development workflows, see **[`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md)**.

## Tests

```bash
cd backend
pip install -r requirements.txt
pytest -q
```

Hand-checkable unit tests on the scheduling logic (single-load, naive baseline, and the
multi-load shared-capacity cases including a hand-verified overlap-forcing scenario and an
intentionally-infeasible one) plus price-fetcher tests covering the live-fetch,
cache-fallback, stale-refusal, and fresh-cache-skips-network paths.

The frontend does not have an automated test suite yet — see
[`CONTRIBUTING.md#known-gaps`](CONTRIBUTING.md#known-gaps) for the intended direction and
current verification approach.

## Documentation

| Document | What's in it |
|---|---|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | System diagram, component responsibilities, data flow, and the reasoning behind non-obvious design decisions |
| [`docs/API.md`](docs/API.md) | Full REST API reference — request/response shapes, status codes |
| [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md) | Setup, configuration, tests, troubleshooting, common workflows |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | How to contribute, project status, known gaps |
| [`SECURITY.md`](SECURITY.md) | Intended deployment scope and how to report a vulnerability |
| [`CHANGELOG.md`](CHANGELOG.md) | Notable changes over time |
| [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) | Community standards |

## Known limitations / MUST BUILD vs NICE TO HAVE

Implemented so far: real aWATTar integration with caching and staleness handling,
single-load optimal scheduling, multi-load shared-capacity scheduling with its own exact
algorithm, naive-baseline comparison, savings computation, PuLP-validated optimality, and
a working frontend (price chart with schedule overlays, appliance form, per-appliance
timeline, savings summary, capacity-usage chart).

Not yet built (see [`CONTRIBUTING.md#known-gaps`](CONTRIBUTING.md#known-gaps) for details
and intended approach): historical savings analysis over real past days, a frontend test
suite, persisted appliance configs, and a CI pipeline.

The backtracking search is worst-case exponential in the number of loads — a documented,
accepted limitation at household scale (single digits of loads), not an oversight.

## Contributing

Contributions, bug reports, and feature requests are welcome — see
**[`CONTRIBUTING.md`](CONTRIBUTING.md)** for the full guide, including the project's
current solo-maintainer status, the development workflow, and what to know before touching
the scheduler or the API contract. Please also review the
[`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).

## License

MIT — see [`LICENSE`](LICENSE).
