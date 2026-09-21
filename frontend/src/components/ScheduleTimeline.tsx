import type { Load, PricePoint, ScheduledRun } from "../types";

interface Props {
  loads: Load[];
  prices: PricePoint[];
  naiveRuns: ScheduledRun[];
  optimizedRuns: ScheduledRun[];
}

function hourLabel(prices: PricePoint[], hour: number): string {
  const p = prices[hour];
  if (!p) return `h${hour}`;
  return new Date(p.start_epoch_ms).toLocaleTimeString(undefined, { hour: "2-digit" });
}

function Bar({
  run,
  horizon,
  color,
}: {
  run: ScheduledRun | undefined;
  horizon: number;
  color: string;
}) {
  if (!run) {
    return <div className="timeline-bar-track" />;
  }
  const left = (run.start_hour / horizon) * 100;
  const width = ((run.end_hour - run.start_hour) / horizon) * 100;
  return (
    <div className="timeline-bar-track">
      <div
        className="timeline-bar"
        style={{ left: `${left}%`, width: `${width}%`, background: color }}
        title={`${run.start_hour}:00–${run.end_hour}:00, €${run.cost_eur.toFixed(3)}`}
      >
        <span>€{run.cost_eur.toFixed(2)}</span>
      </div>
    </div>
  );
}

export function ScheduleTimeline({ loads, prices, naiveRuns, optimizedRuns }: Props) {
  const horizon = prices.length || 24;
  const naiveById = new Map(naiveRuns.map((r) => [r.load_id, r]));
  const optById = new Map(optimizedRuns.map((r) => [r.load_id, r]));

  const tickHours = [0, Math.floor(horizon / 4), Math.floor(horizon / 2), Math.floor((3 * horizon) / 4), horizon - 1];

  return (
    <div className="schedule-timeline">
      <div className="timeline-axis">
        {tickHours.map((h) => (
          <span key={h} style={{ left: `${(h / horizon) * 100}%` }}>
            {hourLabel(prices, h)}
          </span>
        ))}
      </div>
      {loads.map((load) => (
        <div className="timeline-row" key={load.id}>
          <div className="timeline-label">{load.id}</div>
          <div className="timeline-bars">
            <Bar run={naiveById.get(load.id)} horizon={horizon} color="#f97316" />
            <Bar run={optById.get(load.id)} horizon={horizon} color="#22c55e" />
          </div>
        </div>
      ))}
      <div className="timeline-legend">
        <span>
          <i style={{ background: "#f97316" }} /> naive (whenever-convenient)
        </span>
        <span>
          <i style={{ background: "#22c55e" }} /> optimized (capacity-constrained)
        </span>
      </div>
    </div>
  );
}
