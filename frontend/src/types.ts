export interface PricePoint {
  hour_index: number;
  start_epoch_ms: number;
  eur_per_kwh: number;
}

export interface PricesResponse {
  is_stale: boolean;
  prices: PricePoint[];
}

export interface Load {
  id: string;
  duration_hours: number;
  power_kw: number;
  window_start_hour: number;
  window_end_hour: number;
}

export interface ScheduledRun {
  load_id: string;
  start_hour: number;
  end_hour: number;
  cost_eur: number;
}

export interface ScheduleBlock {
  runs: ScheduledRun[];
  total_cost_eur: number;
  infeasible_load_ids: string[];
}

export interface ScheduleResponse {
  is_stale: boolean;
  capacity_kw: number;
  naive: ScheduleBlock;
  single_load_optimal: ScheduleBlock;
  optimized: ScheduleBlock;
  savings_eur_vs_naive: number;
}
