# Development Guide

How to run, test, and modify this project locally. For *why* things are built the way they
are, see [`ARCHITECTURE.md`](ARCHITECTURE.md). For the HTTP contract, see
[`API.md`](API.md).

## Prerequisites

- **Docker + Docker Compose** — the supported way to run the full stack. This project was
  built and is verified against Dockerized services; running the backend/frontend without
  Docker (see [Running without Docker](#running-without-docker-optional) below) works but
  is not the primary, continuously-verified path.
- **Python 3.11+** and **Node.js 20+** — only needed if you want to run backend or frontend
  tooling directly on the host (tests, linting, `tsc`) rather than inside containers.

## Quickstart

```bash
git clone git@github.com:jamnxdev/energy-optimizer.git
cd energy-optimizer
docker compose up --build
```

- Backend: http://localhost:8000 (`/api/health`, `/api/prices`, `/api/schedule`)
- Frontend: http://localhost:5173

`docker compose down` stops both services. Add `-v` to also drop the `price-cache` volume
if you want to force a fresh aWATTar fetch on next start.

## Configuration

All configuration is via environment variables, set in `docker-compose.yml` for the
Dockerized path.

### Backend (`backend/app/main.py`)

| Variable | Default | Meaning |
|---|---|---|
| `PRICE_CACHE_PATH` | `/data/prices.json` | Where the price cache JSON file lives. Mounted to the `price-cache` named volume in `docker-compose.yml` so it survives container restarts. |
| `HOUSEHOLD_CAPACITY_KW` | `11.0` | Default shared power ceiling used when a `/api/schedule` request omits `capacity_kw`. |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated list of allowed origins. Deliberately not `*` — see [`SECURITY.md`](../SECURITY.md). |

### Frontend (`frontend/.env.development`, `frontend/.env.example`)

| Variable | Meaning |
|---|---|
| `VITE_API_BASE` | Base URL the frontend calls for the backend API. Set to `http://localhost:8000` for local dev; passed as a Docker build arg (`VITE_API_BASE`) in `docker-compose.yml` for the containerized frontend since Vite env vars are baked in at build time, not read at runtime. |

## Running without Docker (optional)

### Backend

```bash
cd backend
pip install -r requirements.txt
PRICE_CACHE_PATH=./prices.json uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Vite will serve on http://localhost:5173 and read `VITE_API_BASE` from
`frontend/.env.development`.

## Tests

### Backend

```bash
cd backend
pip install -r requirements.txt
pytest -q
```

Covers:
- `test_scheduler.py` — single-load sliding-window optimum, the naive baseline, and the
  multi-load shared-capacity cases: a hand-verified overlap-forcing scenario (two loads
  whose individually cheapest windows collide under capacity), a generous-capacity case
  that should match the single-load optimum, and an intentionally infeasible case.
- `test_price_fetcher.py` — live fetch, cache fallback on fetch failure, refusal past the
  48h staleness ceiling, and the "fresh cache skips the network entirely" path.

### Frontend

**No automated tests exist yet for the frontend.** This is a known, current gap, not an
oversight to route around — see [`CONTRIBUTING.md`](../CONTRIBUTING.md#known-gaps) for the
intended direction (component tests via Vitest + React Testing Library for
`ApplianceForm`/`ScheduleSummary`'s conditional-warning logic in particular, since those
have real branching behavior worth locking down). Until then, changes to `frontend/src/`
are verified via:

```bash
cd frontend
npx tsc -b --noEmit   # type-check
npm run lint          # oxlint
```

...plus manual verification in a real browser — `tsc`/lint passing is necessary but not
sufficient evidence a UI change actually works.

## Validating the scheduler against a true optimum

`analysis/validate_optimum.py` is a standalone script, not part of the running app or the
test suite. It re-solves the same scheduling problem as a MILP (PuLP + bundled CBC solver)
and compares its answer against `multi_load_schedule()` across randomly generated
scenarios — see [`ARCHITECTURE.md`](ARCHITECTURE.md#why-these-pieces-exist) for why this
exists at all.

```bash
pip install -r backend/requirements.txt
python analysis/validate_optimum.py --scenarios 200
```

Run this after any change to `backend/app/scheduler.py`'s multi-load logic — a passing
`pytest` suite alone does not demonstrate optimality, only correctness on the specific
hand-picked cases the unit tests cover.

## Common workflows

### Adding a new appliance preset to the frontend form

Edit the preset list in `frontend/src/components/ApplianceForm.tsx`. No backend change
needed — presets are just pre-filled form values for the same `Load` shape.

### Changing the capacity default or cache staleness thresholds

- Household capacity default: `HOUSEHOLD_CAPACITY_KW` env var (see
  [Configuration](#configuration) above) — don't hardcode a new default in `main.py`.
- Cache refresh interval / staleness ceiling: `CACHE_MAX_AGE_SECONDS` /
  `STALE_SERVE_AGE_SECONDS` constants at the top of `backend/app/price_fetcher.py`. These
  are deliberately constants, not env vars — they encode a factual claim about aWATTar's
  publish cadence, not a per-deployment preference.

### Adding a field to `Load` or `ScheduledRun`

These are the shapes shared between `backend/app/models.py`, the FastAPI request/response
models in `main.py`, and `frontend/src/types.ts`. All three need updating together, plus
[`docs/API.md`](API.md). See
[`CONTRIBUTING.md`](../CONTRIBUTING.md#when-to-touch-the-api-contract).

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `/api/prices` returns 503 on first run | No cached prices yet and aWATTar is unreachable from your network (corporate proxy, no outbound HTTPS, etc.) — the backend has no synthetic-data fallback by design (see [`ARCHITECTURE.md`](ARCHITECTURE.md#failure-handling-philosophy)). |
| Frontend shows a CORS error in the browser console | `CORS_ORIGINS` on the backend doesn't include the origin the frontend is actually served from. Check it matches exactly (scheme + host + port). |
| A load you added never appears in `optimized` and shows up in `infeasible_load_ids` | Either its own window can't fit its duration, or it genuinely cannot be placed alongside the other configured loads under the current `capacity_kw` — try raising capacity or widening the load's window before assuming a bug. |
| `docker compose up --build` rebuilds but the frontend still serves old JS | Hard-refresh / clear the browser cache — nginx inside the frontend container serves the freshly built static bundle, but browsers cache aggressively by default. |
