import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceArea,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { PricePoint, ScheduledRun } from "../types";

interface Props {
  prices: PricePoint[];
  naiveRuns: ScheduledRun[];
  optimizedRuns: ScheduledRun[];
}

function hourLabel(startEpochMs: number): string {
  return new Date(startEpochMs).toLocaleString(undefined, {
    weekday: "short",
    hour: "2-digit",
  });
}

export function PriceChart({ prices, naiveRuns, optimizedRuns }: Props) {
  const data = prices.map((p) => ({ ...p, label: hourLabel(p.start_epoch_ms) }));

  return (
    <ResponsiveContainer width="100%" height={320}>
      <AreaChart data={data} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="priceFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#6366f1" stopOpacity={0.35} />
            <stop offset="100%" stopColor="#6366f1" stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#2a2a35" />
        <XAxis dataKey="label" interval={3} tick={{ fontSize: 11 }} />
        <YAxis
          tickFormatter={(v: number) => `${v.toFixed(2)}€`}
          width={56}
          tick={{ fontSize: 11 }}
        />
        <Tooltip
          formatter={(value) => [`${Number(value).toFixed(3)} €/kWh`, "price"]}
          labelFormatter={(label) => `Hour: ${label}`}
        />
        <Area type="stepAfter" dataKey="eur_per_kwh" stroke="#6366f1" fill="url(#priceFill)" />
        {naiveRuns.map((r) => (
          <ReferenceArea
            key={`naive-${r.load_id}`}
            x1={data[r.start_hour]?.label}
            x2={data[Math.max(r.end_hour - 1, r.start_hour)]?.label}
            fill="#f97316"
            fillOpacity={0.15}
            ifOverflow="visible"
          />
        ))}
        {optimizedRuns.map((r) => (
          <ReferenceArea
            key={`opt-${r.load_id}`}
            x1={data[r.start_hour]?.label}
            x2={data[Math.max(r.end_hour - 1, r.start_hour)]?.label}
            fill="#22c55e"
            fillOpacity={0.25}
            ifOverflow="visible"
          />
        ))}
      </AreaChart>
    </ResponsiveContainer>
  );
}
