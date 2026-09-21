import {
  Bar,
  BarChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Load, PricePoint, ScheduledRun } from "../types";

interface Props {
  prices: PricePoint[];
  runs: ScheduledRun[];
  loads: Load[];
  capacityKw: number;
}

function hourLabel(startEpochMs: number): string {
  return new Date(startEpochMs).toLocaleString(undefined, { weekday: "short", hour: "2-digit" });
}

/** Per-hour total kW drawn by all scheduled runs -- the thing the shared
 * capacity constraint actually limits. Rendering this alongside the
 * capacity line is what makes "the constraint is respected" checkable by
 * eye, not just asserted by the backend.
 */
export function CapacityChart({ prices, runs, loads, capacityKw }: Props) {
  const powerById = new Map(loads.map((l) => [l.id, l.power_kw]));
  const usageByHour = new Array(prices.length).fill(0);
  for (const run of runs) {
    const powerKw = powerById.get(run.load_id);
    if (powerKw == null) continue;
    for (let h = run.start_hour; h < run.end_hour; h++) {
      if (h >= 0 && h < usageByHour.length) usageByHour[h] += powerKw;
    }
  }

  const data = prices.map((p, i) => ({
    label: hourLabel(p.start_epoch_ms),
    kw: Math.round(usageByHour[i] * 100) / 100,
  }));

  return (
    <ResponsiveContainer width="100%" height={160}>
      <BarChart data={data} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#2a2a35" />
        <XAxis dataKey="label" interval={3} tick={{ fontSize: 11 }} />
        <YAxis tickFormatter={(v: number) => `${v}kW`} width={48} tick={{ fontSize: 11 }} />
        <Tooltip formatter={(value) => [`${value} kW`, "load"]} />
        <ReferenceLine y={capacityKw} stroke="#ef4444" strokeDasharray="4 4" label={{ value: "capacity", fontSize: 11, fill: "#ef4444" }} />
        <Bar dataKey="kw" fill="#6366f1" radius={[2, 2, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
