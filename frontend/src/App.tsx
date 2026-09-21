import { useEffect, useState } from "react";
import "./App.css";
import { fetchPrices, fetchSchedule } from "./api";
import { ApplianceForm } from "./components/ApplianceForm";
import { CapacityChart } from "./components/CapacityChart";
import { PriceChart } from "./components/PriceChart";
import { ScheduleSummary } from "./components/ScheduleSummary";
import { ScheduleTimeline } from "./components/ScheduleTimeline";
import type { Load, PricePoint, ScheduleResponse } from "./types";

function App() {
  const [prices, setPrices] = useState<PricePoint[] | null>(null);
  const [priceError, setPriceError] = useState<string | null>(null);
  const [loads, setLoads] = useState<Load[]>([]);
  const [capacityKw, setCapacityKw] = useState(11);
  const [schedule, setSchedule] = useState<ScheduleResponse | null>(null);
  const [scheduleError, setScheduleError] = useState<string | null>(null);

  useEffect(() => {
    fetchPrices()
      .then((res) => setPrices(res.prices))
      .catch((err) => setPriceError(err.message));
  }, []);

  useEffect(() => {
    if (loads.length === 0) {
      setSchedule(null);
      return;
    }
    fetchSchedule(loads, capacityKw)
      .then((res) => {
        setSchedule(res);
        setScheduleError(null);
      })
      .catch((err) => setScheduleError(err.message));
  }, [loads, capacityKw]);

  const horizonHours = prices?.length ?? 24;

  return (
    <div className="app">
      <header>
        <h1>Dynamic-Tariff Home Energy Scheduler</h1>
        <p className="subtitle">
          Real day-ahead prices from aWATTar. Add appliances below to see the cost of
          running them whenever-convenient (orange) versus an optimized schedule under a
          shared household capacity constraint (green).
        </p>
      </header>

      {priceError && <p className="error">Failed to load prices: {priceError}</p>}

      {prices && (
        <PriceChart
          prices={prices}
          naiveRuns={schedule?.naive.runs ?? []}
          optimizedRuns={schedule?.optimized.runs ?? []}
        />
      )}

      <section>
        <h2>Appliances</h2>
        <ApplianceForm horizonHours={horizonHours} loads={loads} onChange={setLoads} />
      </section>

      <section className="capacity-control">
        <label>
          Household capacity limit (kW):{" "}
          <input
            type="number"
            min={1}
            step={0.5}
            value={capacityKw}
            onChange={(e) => setCapacityKw(Number(e.target.value))}
          />
        </label>
      </section>

      {scheduleError && <p className="error">Failed to compute schedule: {scheduleError}</p>}
      {schedule && <ScheduleSummary schedule={schedule} />}

      {schedule && prices && loads.length > 0 && (
        <section>
          <h2>Schedule</h2>
          <ScheduleTimeline
            loads={loads}
            prices={prices}
            naiveRuns={schedule.naive.runs}
            optimizedRuns={schedule.optimized.runs}
          />
        </section>
      )}

      {schedule && prices && loads.length > 0 && (
        <section>
          <h2>Shared capacity usage (optimized schedule)</h2>
          <p className="subtitle">
            Total household draw per hour under the optimized schedule, against the
            configured capacity limit (red dashed line) — proof the constraint is
            actually respected, not just asserted.
          </p>
          <CapacityChart
            prices={prices}
            runs={schedule.optimized.runs}
            loads={loads}
            capacityKw={schedule.capacity_kw}
          />
        </section>
      )}
    </div>
  );
}

export default App;
