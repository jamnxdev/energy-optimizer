# Dynamic-Tariff Home Energy Scheduling Optimizer

Schedules shiftable household appliance runs (dishwasher, washing machine, EV charging)
against real day-ahead electricity prices from [aWATTar](https://www.awattar.de/) to
minimize cost, and quantifies the savings versus running appliances at a fixed,
"whenever convenient" time.

## Architecture

```
backend/    FastAPI service: aWATTar price fetch + cache, scheduling engine, REST API
frontend/   React + TypeScript UI: live price chart, appliance config, schedule/savings view
analysis/   Standalone script validating the scheduler against a PuLP MILP true optimum
```

Data flow: the backend fetches and caches day-ahead hourly prices from aWATTar → the
frontend lets you configure shiftable loads (duration, power draw, allowed window) → the
backend computes three schedules for the same instance (naive baseline, single-load
optimal, and the full multi-load shared-capacity-constrained schedule) → the frontend
renders all three over the price curve with the cost delta highlighted.

## The scheduling problem

- **Single load:** cheapest contiguous window of a fixed duration within an allowed
  window — a sliding-window minimum, O(hours) per load.
- **Multiple loads sharing one household power limit (the real engineering core):**
  a load's individually cheapest window can collide with another load's cheapest window
  on the same circuit, so placements interact — this is not "sort by cheapest hour."
  Implemented as an exact branch-and-bound backtracking search (most-constrained-load-first
  ordering, cheapest-candidate-first branching, pruned the moment a partial cost can no
  longer beat the best complete solution found). See `backend/app/scheduler.py` for the
  full design rationale in the docstring.
- **Validation:** `analysis/validate_optimum.py` formulates the identical problem as a
  MILP (binary start-time indicators, a capacity constraint per hour) and solves it with
  PuLP/CBC, then compares against the backtracking search's answer across randomly
  generated scenarios. Across 150 generated scenarios (11 infeasible under both methods,
  excluded from cost comparison), the backtracking search matched the true optimum with
  **zero mismatches and zero optimality gap**, running in ~0.1ms median per scenario —
  confirming the search is genuinely exact at household scale, not a heuristic with lucky
  results. Reproduce with:
  ```
  pip install -r backend/requirements.txt
  python analysis/validate_optimum.py --scenarios 200
  ```

## Failure handling

- aWATTar unreachable → serve the last cached prices with an `is_stale` flag rather than
  crash; refuse to serve anything older than 48h (stale data past that point would be
  actively misleading, not just imprecise). See `backend/app/price_fetcher.py`.
- A load whose deadline is infeasible given its duration/window, or that cannot be placed
  under the shared capacity constraint at all → reported explicitly via
  `infeasible_load_ids`, never silently dropped or overcommitted.

## Running locally

```
docker compose up --build
```

- Backend: http://localhost:8000 (`/api/health`, `/api/prices`, `/api/schedule`)
- Frontend: http://localhost:5173

## Tests

```
cd backend
pip install -r requirements.txt
pytest -q
```

Hand-checkable unit tests on the scheduling logic (single-load, naive baseline, and the
multi-load shared-capacity cases including a hand-verified overlap-forcing scenario and an
intentionally-infeasible one) plus price-fetcher tests covering the live-fetch, cache-fallback,
stale-refusal, and fresh-cache-skips-network paths.

## Known limitations / MUST BUILD vs NICE TO HAVE

See `PORTFOLIO_PROJECT_5_ENERGY_OPTIMIZER.md` in the portfolio root for the full spec.
Implemented so far: real aWATTar integration with caching and staleness handling,
single-load optimal scheduling, multi-load shared-capacity scheduling with its own exact
algorithm, naive-baseline comparison, savings computation, PuLP-validated optimality, and
a working frontend (price chart, appliance form, savings summary). Historical savings
analysis over real past days and simple persisted appliance configs remain nice-to-haves.
The backtracking search is worst-case exponential in the number of loads — a documented,
accepted limitation at household scale (single digits of loads), not an oversight.
