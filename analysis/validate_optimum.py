"""Validates the backtracking scheduler (app.scheduler.multi_load_schedule)
against a true MILP optimum computed by PuLP, on randomly generated
scenarios. This is the "optimality gap" metric from the project spec: if
the backtracking search is genuinely exact (as designed), the gap should
be ~0 on every scenario, and any non-zero gap is a real bug to chase down,
not "expected heuristic slack".

Run from the repo root: python -m analysis.validate_optimum --scenarios 200
"""

from __future__ import annotations

import argparse
import random
import statistics
import sys
import time
from pathlib import Path

import pulp

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.models import HourlyPrice, Load  # noqa: E402
from app.scheduler import multi_load_schedule  # noqa: E402


def random_scenario(rng: random.Random, horizon: int = 24, n_loads: int = 4):
    prices = [HourlyPrice(i, i * 3_600_000, round(rng.uniform(-0.05, 0.60), 3)) for i in range(horizon)]
    loads = []
    for i in range(n_loads):
        duration = rng.randint(1, 4)
        window_start = rng.randint(0, horizon - duration)
        window_end = rng.randint(window_start + duration, horizon)
        loads.append(
            Load(
                id=f"load{i}",
                duration_hours=duration,
                power_kw=round(rng.uniform(0.5, 4.0), 1),
                window_start_hour=window_start,
                window_end_hour=window_end,
            )
        )
    capacity_kw = round(rng.uniform(3.0, 10.0), 1)
    return prices, loads, capacity_kw


def milp_optimum(prices: list[HourlyPrice], loads: list[Load], capacity_kw: float) -> float | None:
    """Formulates the same problem as a MILP: binary start-time indicators
    per load, a capacity constraint per hour, minimize total cost. Returns
    None if infeasible (mirrors the backtracking search's own infeasibility
    reporting).
    """
    horizon = len(prices)
    prob = pulp.LpProblem("energy_schedule", pulp.LpMinimize)

    starts: dict[str, list[int]] = {
        load.id: list(range(load.window_start_hour, load.window_end_hour - load.duration_hours + 1))
        for load in loads
    }
    if any(len(s) == 0 for s in starts.values()):
        return None

    x = {
        (load.id, s): pulp.LpVariable(f"x_{load.id}_{s}", cat="Binary")
        for load in loads
        for s in starts[load.id]
    }

    for load in loads:
        prob += pulp.lpSum(x[load.id, s] for s in starts[load.id]) == 1

    for h in range(horizon):
        prob += (
            pulp.lpSum(
                x[load.id, s] * load.power_kw
                for load in loads
                for s in starts[load.id]
                if s <= h < s + load.duration_hours
            )
            <= capacity_kw
        )

    prob += pulp.lpSum(
        x[load.id, s]
        * sum(prices[h].eur_per_kwh for h in range(s, s + load.duration_hours))
        * load.power_kw
        for load in loads
        for s in starts[load.id]
    )

    status = prob.solve(pulp.PULP_CBC_CMD(msg=False))
    if pulp.LpStatus[status] != "Optimal":
        return None
    return pulp.value(prob.objective)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenarios", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    gaps = []
    matched_infeasible = 0
    mismatches = []
    backtrack_times = []

    for i in range(args.scenarios):
        prices, loads, capacity_kw = random_scenario(rng)

        t0 = time.perf_counter()
        ours = multi_load_schedule(prices, loads, capacity_kw)
        backtrack_times.append(time.perf_counter() - t0)

        true_opt = milp_optimum(prices, loads, capacity_kw)

        our_infeasible = bool(ours.infeasible_load_ids)
        milp_infeasible = true_opt is None

        if our_infeasible != milp_infeasible:
            mismatches.append((i, "infeasibility mismatch", ours.infeasible_load_ids, true_opt))
            continue
        if our_infeasible:
            matched_infeasible += 1
            continue

        gap = ours.total_cost_eur - true_opt
        gaps.append(gap)
        if gap > 1e-6:
            mismatches.append((i, "cost gap", ours.total_cost_eur, true_opt))

    print(f"Scenarios: {args.scenarios}")
    print(f"Both infeasible (excluded from gap stats): {matched_infeasible}")
    print(f"Mismatches (should be 0 if the search is truly exact): {len(mismatches)}")
    for m in mismatches[:10]:
        print("  ", m)
    if gaps:
        print(f"Optimality gap (EUR) -- mean: {statistics.mean(gaps):.6f}, max: {max(gaps):.6f}")
    print(
        f"Backtracking search time (s) -- median: {statistics.median(backtrack_times):.4f}, "
        f"p95: {sorted(backtrack_times)[int(0.95 * len(backtrack_times))]:.4f}"
    )


if __name__ == "__main__":
    main()
