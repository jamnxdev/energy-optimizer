# API Reference

Base URL (local dev, via `docker compose`): `http://localhost:8000`

All responses are JSON. There is no authentication — this is a local/portfolio deployment,
not a multi-tenant service; see [`SECURITY.md`](../SECURITY.md) before exposing it publicly.

## `GET /api/health`

Liveness check.

**Response `200`**
```json
{ "status": "ok" }
```

## `GET /api/prices`

Returns the current day-ahead price series (hourly, EUR/kWh), fetched live from aWATTar or
served from cache per the rules in [`ARCHITECTURE.md`](ARCHITECTURE.md#failure-handling-philosophy).

**Response `200`**
```json
{
  "is_stale": false,
  "prices": [
    { "hour_index": 0, "start_epoch_ms": 1732485600000, "eur_per_kwh": 0.2143 },
    { "hour_index": 1, "start_epoch_ms": 1732489200000, "eur_per_kwh": 0.1987 }
  ]
}
```

| Field | Type | Meaning |
|---|---|---|
| `is_stale` | `bool` | `true` if this data did *not* come from a successful live fetch just now (aWATTar was unreachable and a cache fallback was used). |
| `prices[].hour_index` | `int` | 0-based offset into the fetched window. This is the index space `window_start_hour`/`window_end_hour` in `/api/schedule` refer to. |
| `prices[].start_epoch_ms` | `int` | Wall-clock start time of the hour, milliseconds since epoch. |
| `prices[].eur_per_kwh` | `float` | Price for that hour, already converted from aWATTar's EUR/MWh. |

**Error `503`** — aWATTar unreachable *and* no usable cache (absent, or older than 48h):
```json
{ "detail": "aWATTar unreachable and no cached prices available" }
```

## `POST /api/schedule`

Computes and returns three schedules for the same set of loads over the current price
horizon: a naive baseline, the single-load optimum (ignoring shared capacity), and the
full capacity-constrained optimum. See
[`ARCHITECTURE.md`](ARCHITECTURE.md#why-three-schedules-are-computed-on-every-apischedule-call-not-just-the-best-one)
for why all three are returned.

**Request body**
```json
{
  "loads": [
    {
      "id": "dishwasher",
      "duration_hours": 2,
      "power_kw": 1.5,
      "window_start_hour": 0,
      "window_end_hour": 24
    }
  ],
  "capacity_kw": 8.0
}
```

| Field | Type | Required | Meaning |
|---|---|---|---|
| `loads[].id` | `string` | yes | Caller-assigned identifier, echoed back in results. Must be unique per request. |
| `loads[].duration_hours` | `int > 0` | yes | Contiguous hours the appliance needs to run. |
| `loads[].power_kw` | `float > 0` | yes | Power draw while running. |
| `loads[].window_start_hour` | `int ≥ 0` | yes | Earliest hour (inclusive, index into `/api/prices`) the load may start. |
| `loads[].window_end_hour` | `int > 0` | yes | Deadline (exclusive) — the load must finish by this hour. |
| `capacity_kw` | `float` or `null` | no | Shared household power ceiling for the optimized schedule. Defaults to the server's `HOUSEHOLD_CAPACITY_KW` env var (default `11.0`) when omitted. |

**Response `200`**
```json
{
  "is_stale": false,
  "capacity_kw": 8.0,
  "naive": {
    "runs": [{ "load_id": "dishwasher", "start_hour": 0, "end_hour": 2, "cost_eur": 0.62 }],
    "total_cost_eur": 0.62,
    "infeasible_load_ids": []
  },
  "single_load_optimal": { "...": "same shape as naive" },
  "optimized": { "...": "same shape as naive" },
  "savings_eur_vs_naive": 0.18
}
```

`naive`, `single_load_optimal`, and `optimized` all share the same shape:

| Field | Type | Meaning |
|---|---|---|
| `runs[].load_id` | `string` | Matches the request's `loads[].id`. |
| `runs[].start_hour` / `end_hour` | `int` | Scheduled window, `end_hour` exclusive. |
| `runs[].cost_eur` | `float` | Cost of running that load in that window. |
| `total_cost_eur` | `float` | Sum of all `runs[].cost_eur` in this schedule. |
| `infeasible_load_ids` | `string[]` | Load IDs that could not be scheduled under this method — either individually infeasible (duration doesn't fit its own window) or, for `optimized` only, unsatisfiable together under the shared capacity constraint. Never silently dropped; always listed here instead. |

`savings_eur_vs_naive` is `naive.total_cost_eur − optimized.total_cost_eur` — can be `0` if
optimization found no improvement, but is never computed against a different price snapshot
than the schedules themselves.

**Error `422`** — one or more loads' `window_end_hour` exceeds the available price horizon:
```json
{ "detail": "loads ['ev_charger'] have window_end_hour beyond the 24-hour available price horizon" }
```

**Error `503`** — same as `/api/prices`; scheduling can't proceed without a price series.

## Versioning

There is no `/v1` prefix and no version negotiation — this is a single-consumer API (this
repo's own frontend). A breaking change to the request/response shape is acceptable but
must update the frontend in the same change; see
[`CONTRIBUTING.md`](../CONTRIBUTING.md#when-to-touch-the-api-contract).
