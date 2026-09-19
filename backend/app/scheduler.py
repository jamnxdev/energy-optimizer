from __future__ import annotations

from app.models import HourlyPrice, Load, ScheduledRun, ScheduleResult


def _window_cost(prices: list[HourlyPrice], load: Load, start_hour: int) -> float:
    hours = prices[start_hour : start_hour + load.duration_hours]
    return sum(p.eur_per_kwh for p in hours) * load.power_kw


def cheapest_window(prices: list[HourlyPrice], load: Load) -> tuple[int, float]:
    """Single-load case: cheapest contiguous window of `duration_hours`
    within [window_start_hour, window_end_hour) — a sliding-window minimum.

    O(H) per load via a running sum, not O(H * duration) brute force.
    """
    if not load.is_feasible():
        raise ValueError(f"load {load.id} has no feasible start time")

    lo, hi = load.window_start_hour, load.latest_start()
    running = sum(p.eur_per_kwh for p in prices[lo : lo + load.duration_hours]) * load.power_kw
    best_start, best_cost = lo, running

    for start in range(lo + 1, hi + 1):
        leaving = prices[start - 1].eur_per_kwh
        entering = prices[start - 1 + load.duration_hours].eur_per_kwh
        running += (entering - leaving) * load.power_kw
        if running < best_cost:
            best_start, best_cost = start, running

    return best_start, best_cost


def naive_schedule(prices: list[HourlyPrice], loads: list[Load], fixed_start_hour: int = 0) -> ScheduleResult:
    """Baseline: run each load at a fixed convenient time — the earliest
    hour in its allowed window, clamped so it still finishes by its
    deadline. This models "just run it now / at a habitual time" behavior,
    which is what most people actually do without a scheduling tool.
    """
    runs: list[ScheduledRun] = []
    infeasible: list[str] = []
    for load in loads:
        if not load.is_feasible():
            infeasible.append(load.id)
            continue
        start = max(load.window_start_hour, min(fixed_start_hour, load.latest_start()))
        cost = _window_cost(prices, load, start)
        runs.append(ScheduledRun(load.id, start, start + load.duration_hours, cost))
    return ScheduleResult(runs, sum(r.cost_eur for r in runs), infeasible)


def single_load_schedule(prices: list[HourlyPrice], loads: list[Load]) -> ScheduleResult:
    runs: list[ScheduledRun] = []
    infeasible: list[str] = []
    for load in loads:
        if not load.is_feasible():
            infeasible.append(load.id)
            continue
        start, cost = cheapest_window(prices, load)
        runs.append(ScheduledRun(load.id, start, start + load.duration_hours, cost))
    return ScheduleResult(runs, sum(r.cost_eur for r in runs), infeasible)


def _capacity_ok(
    usage: list[float], load: Load, start: int, capacity_kw: float
) -> bool:
    for h in range(start, start + load.duration_hours):
        if usage[h] + load.power_kw > capacity_kw + 1e-9:
            return False
    return True


def _apply(usage: list[float], load: Load, start: int, sign: int) -> None:
    for h in range(start, start + load.duration_hours):
        usage[h] += sign * load.power_kw


def multi_load_schedule(
    prices: list[HourlyPrice], loads: list[Load], capacity_kw: float
) -> ScheduleResult:
    """Multi-load case with a shared power-capacity constraint.

    This is a genuine combinatorial problem, not "sort by cheapest hour":
    a load's cheapest window individually may collide with another load's
    cheapest window on the shared circuit, so placements interact and a
    greedy per-load choice can be globally wrong.

    Approach: exact branch-and-bound backtracking search, not a heuristic.
    - Loads are ordered most-constrained-first (fewest legal start times),
      the standard CSP "minimum remaining values" heuristic — placing the
      least flexible load first prunes the search tree fastest.
    - For each load, candidate start times are tried cheapest-first, so the
      first complete assignment found is already a strong incumbent.
    - A branch is pruned as soon as the partial cost placed so far equals or
      exceeds the best complete solution found (branch and bound), and
      again if a load has zero remaining feasible starts given the
      already-placed loads' capacity usage.

    This is only exact-search feasible because household-scale inputs are
    small (a handful of loads, day-ahead windows of ~24-48 hours) — it is
    validated for correctness against a PuLP MILP formulation on generated
    scenarios (see analysis/validate_optimum.py), not assumed correct.
    Worst case is exponential in the number of loads; at real household
    scale (single digits) this is not a practical concern, and is a known,
    documented limitation rather than an oversight.
    """
    feasible_loads = [l for l in loads if l.is_feasible()]
    infeasible = [l.id for l in loads if not l.is_feasible()]
    if not feasible_loads:
        return ScheduleResult([], 0.0, infeasible)

    horizon = len(prices)
    usage = [0.0] * horizon

    candidates: dict[str, list[tuple[int, float]]] = {}
    for load in feasible_loads:
        starts = []
        for s in range(load.window_start_hour, load.latest_start() + 1):
            starts.append((s, _window_cost(prices, load, s)))
        starts.sort(key=lambda t: t[1])
        candidates[load.id] = starts

    still_infeasible = [l.id for l in feasible_loads if not candidates[l.id]]
    feasible_loads = [l for l in feasible_loads if candidates[l.id]]
    infeasible.extend(still_infeasible)

    order = sorted(feasible_loads, key=lambda l: len(candidates[l.id]))

    best: dict[str, object] = {"cost": float("inf"), "assignment": None}
    assignment: dict[str, int] = {}

    def backtrack(idx: int, cost_so_far: float) -> None:
        if cost_so_far >= best["cost"]:
            return
        if idx == len(order):
            best["cost"] = cost_so_far
            best["assignment"] = dict(assignment)
            return

        load = order[idx]
        for start, window_cost in candidates[load.id]:
            new_cost = cost_so_far + window_cost
            if new_cost >= best["cost"]:
                break  # candidates sorted by cost ascending: no point continuing
            if not _capacity_ok(usage, load, start, capacity_kw):
                continue
            _apply(usage, load, start, +1)
            assignment[load.id] = start
            backtrack(idx + 1, new_cost)
            _apply(usage, load, start, -1)
            del assignment[load.id]

    backtrack(0, 0.0)

    if best["assignment"] is None:
        # Could not simultaneously satisfy every load's window under the
        # shared capacity constraint. Surface as infeasible rather than
        # silently dropping loads or exceeding capacity.
        return ScheduleResult([], 0.0, infeasible + [l.id for l in feasible_loads])

    runs = [
        ScheduledRun(
            load.id,
            best["assignment"][load.id],
            best["assignment"][load.id] + load.duration_hours,
            _window_cost(prices, load, best["assignment"][load.id]),
        )
        for load in feasible_loads
    ]
    return ScheduleResult(runs, best["cost"], infeasible)
