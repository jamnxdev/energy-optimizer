from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HourlyPrice:
    """One hour of day-ahead market price, already converted to EUR/kWh."""

    hour_index: int  # 0-based offset from the start of the fetched window
    start_epoch_ms: int
    eur_per_kwh: float


@dataclass(frozen=True)
class Load:
    """A shiftable household appliance run."""

    id: str
    duration_hours: int
    power_kw: float
    window_start_hour: int  # inclusive, index into the price series
    window_end_hour: int  # exclusive upper bound; deadline = this hour

    def latest_start(self) -> int:
        return self.window_end_hour - self.duration_hours

    def is_feasible(self) -> bool:
        return self.latest_start() >= self.window_start_hour


@dataclass(frozen=True)
class ScheduledRun:
    load_id: str
    start_hour: int
    end_hour: int  # exclusive
    cost_eur: float


@dataclass(frozen=True)
class ScheduleResult:
    runs: list[ScheduledRun]
    total_cost_eur: float
    infeasible_load_ids: list[str]
