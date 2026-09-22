# Architecture

This document explains how the system fits together, why it's shaped the way it is, and
where to look when you need to change something. For "how do I run this," see
[`DEVELOPMENT.md`](DEVELOPMENT.md). For the wire format, see [`API.md`](API.md).

## Overview

```
                         ┌─────────────────────┐
                         │   aWATTar day-ahead  │
                         │   market price API   │
                         └──────────┬───────────┘
                                    │ HTTPS, hourly EUR/MWh
                                    ▼
┌───────────────────────────────────────────────────────┐
│ backend/ (FastAPI)                                     │
│                                                         │
│  price_fetcher.py                                      │
│    PriceFetcher.get_prices() ──► disk cache (JSON)      │
│    live fetch → cache write → convert EUR/MWh→EUR/kWh   │
│    live fetch fails → serve cache, flag is_stale=true   │
│    cache older than 48h → refuse (raise, HTTP 503)      │
│                                                         │
│  scheduler.py                                           │
│    naive_schedule()          — fixed "just run it" time │
│    single_load_schedule()    — sliding-window minimum   │
│    multi_load_schedule()     — backtracking search under │
│                                 a shared capacity limit  │
│                                                         │
│  main.py                                                │
│    GET  /api/health                                     │
│    GET  /api/prices                                      │
│    POST /api/schedule  → runs all three schedulers,      │
│                           returns runs + savings delta    │
└───────────────────────┬───────────────────────────────┘
                         │ JSON over HTTP, CORS-restricted
                         ▼
┌───────────────────────────────────────────────────────┐
│ frontend/ (React + TypeScript + Vite)                   │
│                                                         │
│  api.ts            — thin fetch wrapper, one function    │
│                       per endpoint                       │
│  App.tsx           — owns loads[]/schedule state, wires   │
│                       form → API → charts                 │
│  ApplianceForm     — add/edit shiftable loads              │
│  PriceChart        — price curve + naive/optimized         │
│                       schedule overlays                    │
│  ScheduleTimeline  — per-appliance Gantt-style bars         │
│  CapacityChart     — per-hour kW usage vs. capacity limit    │
│  ScheduleSummary   — € and % savings, warnings               │
└───────────────────────────────────────────────────────┘

analysis/validate_optimum.py (offline, not part of the running app)
  Re-implements the identical scheduling problem as a MILP (PuLP/CBC) and
  compares its optimum against multi_load_schedule() across randomly
  generated scenarios. This is what justifies calling the backtracking
  search "exact" rather than "probably fine."
```

## Why these pieces exist

### Why a disk cache in front of aWATTar, not just fetch-on-request

aWATTar publishes next-day prices once per day. Fetching on every request would hit their
API far more than necessary and would turn *their* availability into *this app's*
availability with no benefit. The cache also gives the failure-handling story somewhere to
fall back to — see [Failure handling](#failure-handling-philosophy) below.

### Why three schedules are computed on every `/api/schedule` call, not just the "best" one

The naive and single-load schedules aren't dead code paths — they are the baseline the
optimized schedule is measured against. `savings_eur_vs_naive` only means something because
the naive schedule is computed from the same inputs, the same prices, the same instant. If
the frontend only ever saw the optimized answer, there would be no honest savings number to
show, only an assertion.

### Why the multi-load scheduler is a hand-written backtracking search instead of calling a solver directly in the request path

Two reasons, one practical and one architectural:

1. **It has to run inside an HTTP request**, synchronously, for interactive use. A general
   MILP solver invocation (spinning up PuLP + CBC) is fine for offline validation but is
   heavier and less predictable in latency than a purpose-built search over a small,
   structured problem.
2. **It has to be exact, not heuristic**, because the whole point of the app is a
   trustworthy savings number — see the scheduling algorithm section in the
   [README](../README.md#the-scheduling-problem). "Exact" is a claim that needs evidence,
   which is exactly what `analysis/validate_optimum.py` provides, decoupled from the
   request path.

The tradeoff: the backtracking search is worst-case exponential in the number of loads.
This is fine at household scale (a handful of shiftable appliances) and is a known,
accepted limitation — not something to "fix" by swapping in a heuristic that would then
need its own correctness argument.

### Why `ScheduledRun` doesn't carry `power_kw`

The frontend already has `power_kw` for every load in its own `loads` state — it's the
same data the request was built from. Echoing it back in the response would be redundant
data crossing the network for no informational gain; `CapacityChart` joins it client-side
by `load_id` instead. If a future consumer of `/api/schedule` doesn't have that context
(e.g., a CLI or a different frontend), this would need revisiting — see
[`CONTRIBUTING.md`](../CONTRIBUTING.md#when-to-touch-the-api-contract).

### Why the frontend has no state management library

`App.tsx` owns `loads` and `schedule` as local `useState`, passed down as props. The
component tree is three levels deep at most and nothing is shared outside a single page —
Redux/Zustand/Context would be structure with no problem to solve yet. If the app grows a
second page or genuinely cross-cutting state, that calculus changes; see
[`CONTRIBUTING.md`](../CONTRIBUTING.md#adding-a-dependency).

## Failure-handling philosophy

Two failure modes are treated as first-class, not edge cases bolted on afterward:

| Failure | Behavior | Where |
|---|---|---|
| aWATTar unreachable, cache fresh enough | Serve cache, `is_stale: true` | `price_fetcher.py` |
| aWATTar unreachable, cache absent or >48h old | Fail loudly (`PriceFetchError` → HTTP 503) | `price_fetcher.py` |
| A load's window/duration is individually infeasible (deadline earlier than duration allows) | Reported in `infeasible_load_ids`, excluded from cost totals | `scheduler.py` |
| Loads individually feasible but unsatisfiable together under shared capacity | Reported in `infeasible_load_ids` for the *optimized* schedule specifically, not silently dropped or overcommitted | `scheduler.py` |
| Requested load window extends beyond the available price horizon | HTTP 422 with the offending load IDs, not a silent truncation | `main.py` |

The unifying rule: **degrade visibly, never silently**. A stale flag the frontend ignores
is still better than a stale flag that doesn't exist. See
[`ScheduleSummary.tsx`](../frontend/src/components/ScheduleSummary.tsx) for how these
signals actually reach the user.

## Data flow: a single `/api/schedule` request

1. User adds/edits loads in `ApplianceForm` → `App.tsx` state.
2. `App.tsx` calls `fetchSchedule(loads, capacityKw)` (`api.ts`).
3. Backend (`main.py`):
   a. Fetches prices (`price_fetcher.py`), returns 503 if truly unavailable.
   b. Validates every load's window fits within the price horizon (422 if not).
   c. Runs `naive_schedule`, `single_load_schedule`, `multi_load_schedule` — same
      `prices`/`loads` input to all three.
   d. Serializes all three results plus `savings_eur_vs_naive = naive.total − optimized.total`.
4. Frontend receives the response, renders:
   - `PriceChart` — price curve with naive (orange) vs. optimized (green) overlays.
   - `ScheduleTimeline` — one Gantt row per load.
   - `CapacityChart` — per-hour kW draw vs. the capacity line, joined with `power_kw`
     from local `loads` state.
   - `ScheduleSummary` — headline savings, warnings for `is_stale` / `infeasible_load_ids`.

## Repository layout

```
backend/     FastAPI service — price fetching/caching, scheduling engine, REST API
frontend/    React + TypeScript UI
analysis/    Standalone MILP validation script (not part of the running app)
docs/        This file, API reference, development guide
```

See [`README.md`](../README.md) for the top-level project description and
[`CONTRIBUTING.md`](../CONTRIBUTING.md) for how to work on any of this.
