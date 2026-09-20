from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.models import Load
from app.price_fetcher import PriceCache, PriceFetcher, PriceFetchError
from app.scheduler import multi_load_schedule, naive_schedule, single_load_schedule

CACHE_PATH = Path(os.environ.get("PRICE_CACHE_PATH", "/data/prices.json"))
DEFAULT_CAPACITY_KW = float(os.environ.get("HOUSEHOLD_CAPACITY_KW", "11.0"))

app = FastAPI(title="Energy Tariff Scheduling Optimizer")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

_fetcher = PriceFetcher(PriceCache(CACHE_PATH))


class LoadIn(BaseModel):
    id: str
    duration_hours: int = Field(gt=0)
    power_kw: float = Field(gt=0)
    window_start_hour: int = Field(ge=0)
    window_end_hour: int = Field(gt=0)


class ScheduleRequest(BaseModel):
    loads: list[LoadIn]
    capacity_kw: float | None = None


@app.get("/api/prices")
def get_prices():
    try:
        prices, is_stale = _fetcher.get_prices()
    except PriceFetchError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {
        "is_stale": is_stale,
        "prices": [
            {"hour_index": p.hour_index, "start_epoch_ms": p.start_epoch_ms, "eur_per_kwh": p.eur_per_kwh}
            for p in prices
        ],
    }


@app.post("/api/schedule")
def post_schedule(req: ScheduleRequest):
    try:
        prices, is_stale = _fetcher.get_prices()
    except PriceFetchError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    horizon = len(prices)
    loads = [Load(**l.model_dump()) for l in req.loads]

    out_of_range = [l.id for l in loads if l.window_end_hour > horizon]
    if out_of_range:
        raise HTTPException(
            status_code=422,
            detail=f"loads {out_of_range} have window_end_hour beyond the {horizon}-hour available price horizon",
        )

    capacity_kw = req.capacity_kw or DEFAULT_CAPACITY_KW

    naive = naive_schedule(prices, loads)
    single = single_load_schedule(prices, loads)
    optimized = multi_load_schedule(prices, loads, capacity_kw)

    def serialize(result):
        return {
            "runs": [
                {"load_id": r.load_id, "start_hour": r.start_hour, "end_hour": r.end_hour, "cost_eur": r.cost_eur}
                for r in result.runs
            ],
            "total_cost_eur": result.total_cost_eur,
            "infeasible_load_ids": result.infeasible_load_ids,
        }

    return {
        "is_stale": is_stale,
        "capacity_kw": capacity_kw,
        "naive": serialize(naive),
        "single_load_optimal": serialize(single),
        "optimized": serialize(optimized),
        "savings_eur_vs_naive": naive.total_cost_eur - optimized.total_cost_eur,
    }


@app.get("/api/health")
def health():
    return {"status": "ok"}
