import pytest

from app.models import HourlyPrice, Load
from app.scheduler import (
    cheapest_window,
    multi_load_schedule,
    naive_schedule,
    single_load_schedule,
)


def prices(values: list[float]) -> list[HourlyPrice]:
    return [HourlyPrice(i, i * 3_600_000, v) for i, v in enumerate(values)]


def test_cheapest_window_hand_checkable():
    # Hours: 0.30 0.10 0.10 0.40 0.05 0.05 0.50 -> duration 2, window [0,7)
    p = prices([0.30, 0.10, 0.10, 0.40, 0.05, 0.05, 0.50])
    load = Load("dishwasher", duration_hours=2, power_kw=1.0, window_start_hour=0, window_end_hour=7)
    start, cost = cheapest_window(p, load)
    assert start == 4  # hours 4,5 = 0.05+0.05 = 0.10, cheapest 2h window
    assert cost == pytest.approx(0.10)


def test_cheapest_window_respects_window_bounds():
    p = prices([0.01, 0.01, 0.01, 0.90, 0.90])
    # cheapest overall window is hours 0-1, but this load isn't allowed to
    # start before hour 3
    load = Load("ev", duration_hours=2, power_kw=1.0, window_start_hour=3, window_end_hour=5)
    start, cost = cheapest_window(p, load)
    assert start == 3
    assert cost == 0.90 + 0.90


def test_infeasible_load_reported_not_silently_dropped():
    p = prices([0.1] * 5)
    load = Load("dryer", duration_hours=4, power_kw=1.0, window_start_hour=2, window_end_hour=5)
    result = single_load_schedule(p, [load])
    assert result.runs == []
    assert result.infeasible_load_ids == ["dryer"]


def test_naive_schedule_uses_earliest_slot_clamped_to_deadline():
    p = prices([0.5, 0.1, 0.1, 0.1])
    load = Load("washer", duration_hours=2, power_kw=1.0, window_start_hour=1, window_end_hour=4)
    result = naive_schedule(p, [load], fixed_start_hour=0)
    run = result.runs[0]
    assert run.start_hour == 1  # clamped up to window_start_hour, not hour 0
    assert run.cost_eur == 0.1 + 0.1


def test_single_load_beats_or_matches_naive_on_same_instance():
    p = prices([0.5, 0.05, 0.05, 0.5, 0.5])
    load = Load("dishwasher", duration_hours=2, power_kw=1.0, window_start_hour=0, window_end_hour=5)
    naive = naive_schedule(p, [load], fixed_start_hour=0)
    optimized = single_load_schedule(p, [load])
    assert optimized.total_cost_eur <= naive.total_cost_eur


def test_multi_load_shared_capacity_forces_loads_apart():
    # Flat prices so cost doesn't drive placement -- only the capacity
    # constraint should. Two 2kW loads on a 3kW circuit cannot overlap.
    p = prices([0.10, 0.10, 0.10, 0.10])
    loads = [
        Load("a", duration_hours=2, power_kw=2.0, window_start_hour=0, window_end_hour=4),
        Load("b", duration_hours=2, power_kw=2.0, window_start_hour=0, window_end_hour=4),
    ]
    result = multi_load_schedule(p, loads, capacity_kw=3.0)
    runs_by_id = {r.load_id: r for r in result.runs}
    a, b = runs_by_id["a"], runs_by_id["b"]
    overlap = range(max(a.start_hour, b.start_hour), min(a.end_hour, b.end_hour))
    assert len(list(overlap)) == 0


def test_multi_load_prefers_cheap_hours_when_capacity_allows_overlap():
    p = prices([0.10, 0.90, 0.90, 0.10])
    loads = [
        Load("a", duration_hours=1, power_kw=1.0, window_start_hour=0, window_end_hour=4),
        Load("b", duration_hours=1, power_kw=1.0, window_start_hour=0, window_end_hour=4),
    ]
    # generous capacity: both loads can run in the same cheap hour
    result = multi_load_schedule(p, loads, capacity_kw=10.0)
    assert result.total_cost_eur == 0.10 + 0.10
    assert {r.start_hour for r in result.runs} == {0}


def test_multi_load_reports_infeasible_when_capacity_cannot_satisfy_all_windows():
    p = prices([0.10, 0.10])
    loads = [
        Load("a", duration_hours=2, power_kw=2.0, window_start_hour=0, window_end_hour=2),
        Load("b", duration_hours=2, power_kw=2.0, window_start_hour=0, window_end_hour=2),
    ]
    # both loads must run the full window, capacity forces them apart, but
    # neither has room to shift -- genuinely infeasible under the constraint
    result = multi_load_schedule(p, loads, capacity_kw=3.0)
    assert result.runs == []
    assert set(result.infeasible_load_ids) == {"a", "b"}


def test_multi_load_matches_single_load_optimum_when_capacity_never_binds():
    p = prices([0.30, 0.10, 0.10, 0.40, 0.05, 0.05, 0.50])
    loads = [Load("solo", duration_hours=2, power_kw=1.0, window_start_hour=0, window_end_hour=7)]
    single = single_load_schedule(p, loads)
    multi = multi_load_schedule(p, loads, capacity_kw=100.0)
    assert multi.total_cost_eur == pytest.approx(single.total_cost_eur)
