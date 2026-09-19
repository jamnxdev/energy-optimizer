import json
import time

import httpx
import pytest

from app.price_fetcher import (
    CACHE_MAX_AGE_SECONDS,
    STALE_SERVE_AGE_SECONDS,
    PriceCache,
    PriceFetchError,
    PriceFetcher,
)

RAW_ROW = {"start_timestamp": 1_700_000_000_000, "end_timestamp": 1_700_003_600_000, "marketprice": 123.4, "unit": "Eur/MWh"}


def make_client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_fetch_live_converts_units_and_caches(tmp_path):
    def handler(request):
        return httpx.Response(200, json={"object": "list", "data": [RAW_ROW]})

    cache = PriceCache(tmp_path / "prices.json")
    fetcher = PriceFetcher(cache, client=make_client(handler))

    prices, is_stale = fetcher.get_prices()

    assert is_stale is False
    assert prices[0].eur_per_kwh == pytest.approx(0.1234)
    assert cache.read() is not None


def test_falls_back_to_cache_when_api_unreachable(tmp_path):
    # Cache is older than the refresh interval, so a live fetch is due --
    # but the network call fails, so it should fall back and flag stale.
    cache_path = tmp_path / "prices.json"
    payload = {"data": [RAW_ROW], "fetched_at": time.time() - CACHE_MAX_AGE_SECONDS - 60}
    cache_path.write_text(json.dumps(payload))
    cache = PriceCache(cache_path)

    def handler(request):
        raise httpx.ConnectError("network down", request=request)

    fetcher = PriceFetcher(cache, client=make_client(handler))
    prices, is_stale = fetcher.get_prices()

    assert prices[0].eur_per_kwh == pytest.approx(0.1234)
    assert is_stale is True  # served from cache, must be flagged


def test_raises_when_unreachable_and_no_cache(tmp_path):
    cache = PriceCache(tmp_path / "prices.json")

    def handler(request):
        raise httpx.ConnectError("network down", request=request)

    fetcher = PriceFetcher(cache, client=make_client(handler))

    with pytest.raises(PriceFetchError):
        fetcher.get_prices()


def test_refuses_to_serve_cache_older_than_hard_limit(tmp_path):
    cache_path = tmp_path / "prices.json"
    payload = {"data": [RAW_ROW], "fetched_at": time.time() - STALE_SERVE_AGE_SECONDS - 60}
    cache_path.write_text(json.dumps(payload))
    cache = PriceCache(cache_path)

    def handler(request):
        raise httpx.ConnectError("network down", request=request)

    fetcher = PriceFetcher(cache, client=make_client(handler))

    with pytest.raises(PriceFetchError):
        fetcher.get_prices()


def test_fresh_cache_is_served_without_hitting_the_network(tmp_path):
    cache_path = tmp_path / "prices.json"
    payload = {"data": [RAW_ROW], "fetched_at": time.time() - (CACHE_MAX_AGE_SECONDS - 60)}
    cache_path.write_text(json.dumps(payload))
    cache = PriceCache(cache_path)

    def handler(request):
        raise AssertionError("should not hit network when cache is fresh")

    fetcher = PriceFetcher(cache, client=make_client(handler))
    prices, is_stale = fetcher.get_prices()

    assert is_stale is False
    assert prices[0].eur_per_kwh == pytest.approx(0.1234)
