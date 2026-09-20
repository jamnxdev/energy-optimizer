import type { Load, PricesResponse, ScheduleResponse } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

async function unwrap<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail ?? `${res.status} ${res.statusText}`);
  }
  return res.json();
}

export function fetchPrices(): Promise<PricesResponse> {
  return fetch(`${API_BASE}/api/prices`).then(unwrap<PricesResponse>);
}

export function fetchSchedule(loads: Load[], capacityKw: number): Promise<ScheduleResponse> {
  return fetch(`${API_BASE}/api/schedule`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ loads, capacity_kw: capacityKw }),
  }).then(unwrap<ScheduleResponse>);
}
