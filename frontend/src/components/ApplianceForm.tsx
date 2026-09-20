import { useState } from "react";
import type { Load } from "../types";

interface Props {
  horizonHours: number;
  loads: Load[];
  onChange: (loads: Load[]) => void;
}

const PRESETS: Omit<Load, "id">[] = [
  { duration_hours: 2, power_kw: 1.5, window_start_hour: 0, window_end_hour: 24 },
  { duration_hours: 1, power_kw: 2.0, window_start_hour: 0, window_end_hour: 24 },
  { duration_hours: 6, power_kw: 3.6, window_start_hour: 0, window_end_hour: 24 },
];
const PRESET_LABELS = ["Dishwasher", "Washing machine", "EV charge"];

export function ApplianceForm({ horizonHours, loads, onChange }: Props) {
  const [nextId, setNextId] = useState(1);

  function addLoad(presetIndex: number) {
    const preset = PRESETS[presetIndex];
    const id = `${PRESET_LABELS[presetIndex].toLowerCase().replace(/\s+/g, "-")}-${nextId}`;
    setNextId((n) => n + 1);
    onChange([
      ...loads,
      { ...preset, id, window_end_hour: Math.min(preset.window_end_hour, horizonHours) },
    ]);
  }

  function updateLoad(id: string, patch: Partial<Load>) {
    onChange(loads.map((l) => (l.id === id ? { ...l, ...patch } : l)));
  }

  function removeLoad(id: string) {
    onChange(loads.filter((l) => l.id !== id));
  }

  return (
    <div className="appliance-form">
      <div className="preset-buttons">
        {PRESET_LABELS.map((label, i) => (
          <button key={label} onClick={() => addLoad(i)} type="button">
            + {label}
          </button>
        ))}
      </div>
      <table>
        <thead>
          <tr>
            <th>Appliance</th>
            <th>Duration (h)</th>
            <th>Power (kW)</th>
            <th>Window start</th>
            <th>Deadline (h)</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {loads.map((load) => (
            <tr key={load.id}>
              <td>{load.id}</td>
              <td>
                <input
                  type="number"
                  min={1}
                  value={load.duration_hours}
                  onChange={(e) => updateLoad(load.id, { duration_hours: Number(e.target.value) })}
                />
              </td>
              <td>
                <input
                  type="number"
                  step={0.1}
                  min={0.1}
                  value={load.power_kw}
                  onChange={(e) => updateLoad(load.id, { power_kw: Number(e.target.value) })}
                />
              </td>
              <td>
                <input
                  type="number"
                  min={0}
                  max={horizonHours}
                  value={load.window_start_hour}
                  onChange={(e) => updateLoad(load.id, { window_start_hour: Number(e.target.value) })}
                />
              </td>
              <td>
                <input
                  type="number"
                  min={1}
                  max={horizonHours}
                  value={load.window_end_hour}
                  onChange={(e) => updateLoad(load.id, { window_end_hour: Number(e.target.value) })}
                />
              </td>
              <td>
                <button type="button" onClick={() => removeLoad(load.id)} aria-label="remove">
                  ×
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
