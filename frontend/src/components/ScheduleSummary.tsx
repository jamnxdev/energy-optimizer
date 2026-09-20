import type { ScheduleResponse } from "../types";

export function ScheduleSummary({ schedule }: { schedule: ScheduleResponse }) {
  const pct =
    schedule.naive.total_cost_eur > 0
      ? (schedule.savings_eur_vs_naive / schedule.naive.total_cost_eur) * 100
      : 0;

  const allInfeasible = new Set([
    ...schedule.naive.infeasible_load_ids,
    ...schedule.optimized.infeasible_load_ids,
  ]);

  return (
    <div className="schedule-summary">
      <div className="savings-headline">
        <span className="savings-amount">€{schedule.savings_eur_vs_naive.toFixed(3)}</span>
        <span className="savings-pct">({pct.toFixed(1)}% saved vs. naive)</span>
      </div>
      <div className="cost-row">
        <span>Naive baseline: €{schedule.naive.total_cost_eur.toFixed(3)}</span>
        <span>Optimized: €{schedule.optimized.total_cost_eur.toFixed(3)}</span>
        <span>Household capacity: {schedule.capacity_kw} kW</span>
      </div>
      {allInfeasible.size > 0 && (
        <p className="infeasible-warning">
          Could not schedule: {[...allInfeasible].join(", ")} — window too short for the
          shared capacity constraint or duration.
        </p>
      )}
      {schedule.is_stale && (
        <p className="stale-warning">Price data is stale — aWATTar was unreachable, showing last-known prices.</p>
      )}
    </div>
  );
}
