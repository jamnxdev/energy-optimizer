from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict
from pathlib import Path

import httpx

from app.models import HourlyPrice

logger = logging.getLogger(__name__)

AWATTAR_URL = "https://api.awattar.de/v1/marketdata"
CACHE_MAX_AGE_SECONDS = 6 * 3600  # aWATTar publishes next-day prices once daily
STALE_SERVE_AGE_SECONDS = 48 * 3600  # refuse to serve anything older than this


class PriceFetchError(Exception):
    pass


class PriceCache:
    """Disk-backed cache of the raw aWATTar response.

    Kept deliberately simple (one JSON file, not per-day partitioning): the
    fetched window already spans multiple days and aWATTar itself is the
    source of truth for what "today"/"tomorrow" mean, so re-fetching and
    overwriting is simpler than merging day-partitioned caches.
    """

    def __init__(self, cache_path: Path):
        self.cache_path = cache_path

    def read(self) -> tuple[list[dict], float] | None:
        if not self.cache_path.exists():
            return None
        try:
            payload = json.loads(self.cache_path.read_text())
            return payload["data"], payload["fetched_at"]
        except (json.JSONDecodeError, KeyError, OSError):
            logger.warning("Price cache at %s is corrupt; ignoring", self.cache_path)
            return None

    def write(self, data: list[dict]) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"data": data, "fetched_at": time.time()}
        tmp_path = self.cache_path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(payload))
        tmp_path.replace(self.cache_path)


class PriceFetcher:
    """Fetches day-ahead prices from aWATTar, with a cache fallback.

    Failure handling per the project spec: if the API is unreachable, serve
    the last-known cached prices with a staleness flag rather than crash or
    silently pretend the data is fresh. Only refuse outright if there is no
    usable cache at all (nothing to fall back to) or the cache itself is
    older than STALE_SERVE_AGE_SECONDS (past that point stale data would be
    actively misleading, not just imprecise).
    """

    def __init__(self, cache: PriceCache, client: httpx.Client | None = None):
        self.cache = cache
        self._client = client or httpx.Client(timeout=10.0)

    def get_prices(self) -> tuple[list[HourlyPrice], bool]:
        """Returns (prices, is_stale). `is_stale` is True whenever the data
        being served did not come from a successful live fetch just now --
        either because the cache was still within its normal refresh
        interval (not stale, just not re-fetched) is the *only* False case;
        any fallback after a failed live fetch is always flagged, even if
        the cache happens to still be fairly recent, since it means today's
        expected refresh did not happen.
        """
        cached = self.cache.read()
        cache_age = time.time() - cached[1] if cached else None

        if cache_age is None or cache_age > CACHE_MAX_AGE_SECONDS:
            try:
                raw = self._fetch_live()
                self.cache.write(raw)
                return self._to_hourly_prices(raw), False
            except (httpx.HTTPError, ValueError) as exc:
                logger.warning("aWATTar fetch failed (%s); falling back to cache", exc)
                if cached is None:
                    raise PriceFetchError(
                        "aWATTar unreachable and no cached prices available"
                    ) from exc

            raw, fetched_at = cached
            age = time.time() - fetched_at
            if age > STALE_SERVE_AGE_SECONDS:
                raise PriceFetchError(
                    f"aWATTar unreachable and cached prices are {age / 3600:.1f}h old "
                    f"(limit {STALE_SERVE_AGE_SECONDS / 3600:.0f}h)"
                )
            return self._to_hourly_prices(raw), True

        raw, _ = cached
        return self._to_hourly_prices(raw), False

    def _fetch_live(self) -> list[dict]:
        response = self._client.get(AWATTAR_URL)
        response.raise_for_status()
        body = response.json()
        data = body.get("data")
        if not data:
            raise ValueError("aWATTar response had no data")
        return data

    @staticmethod
    def _to_hourly_prices(raw: list[dict]) -> list[HourlyPrice]:
        ordered = sorted(raw, key=lambda r: r["start_timestamp"])
        return [
            HourlyPrice(
                hour_index=i,
                start_epoch_ms=row["start_timestamp"],
                eur_per_kwh=row["marketprice"] / 1000.0,  # EUR/MWh -> EUR/kWh
            )
            for i, row in enumerate(ordered)
        ]
