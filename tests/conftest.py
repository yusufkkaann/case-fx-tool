from __future__ import annotations

from datetime import date
from typing import Callable, Optional

import httpx
import pytest
from fastapi.testclient import TestClient

from app.cache import TTLCache
from app.main import create_app
from app.service import ConversionService
from app.upstream import FrankfurterClient

DEFAULT_CURRENCIES = {"EUR": "Euro", "USD": "US Dollar", "TRY": "Turkish Lira", "GBP": "British Pound"}
DEFAULT_TODAY = date(2026, 8, 31)


class FakeUpstream:
    """In-process stand-in for the Frankfurter API. No socket is ever opened.

    ``weekend_map`` lets a test say "a rate asked for day X actually belongs to
    day Y", which is how we exercise the ECB weekend/holiday fallback.
    """

    def __init__(
        self,
        rate: float = 47.1234,
        latest_date: str = "2026-08-31",
        currencies: Optional[dict] = None,
        weekend_map: Optional[dict[str, str]] = None,
    ) -> None:
        self.rate = rate
        self.latest_date = latest_date
        self.currencies = DEFAULT_CURRENCIES if currencies is None else currencies
        self.weekend_map = weekend_map or {}
        self.calls: dict[str, int] = {"currencies": 0, "rate": 0}

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/v1/currencies":
            self.calls["currencies"] += 1
            return httpx.Response(200, json=self.currencies)

        self.calls["rate"] += 1
        symbol = request.url.params.get("symbols", "TRY")
        if path == "/v1/latest":
            rate_date = self.latest_date
        else:
            asked = path.rsplit("/", 1)[-1]
            rate_date = self.weekend_map.get(asked, asked)
        return httpx.Response(
            200,
            json={"amount": 1.0, "base": request.url.params.get("base"), "date": rate_date, "rates": {symbol: self.rate}},
        )


def build_client(
    handler: Callable[[httpx.Request], httpx.Response],
    today: date = DEFAULT_TODAY,
    latest_ttl: float = 3600.0,
) -> TestClient:
    httpx_client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://upstream.test")
    service = ConversionService(
        FrankfurterClient(httpx_client, "http://upstream.test"),
        TTLCache(),
        latest_ttl=latest_ttl,
        today=lambda: today,
    )
    return TestClient(create_app(service))


@pytest.fixture
def upstream() -> FakeUpstream:
    return FakeUpstream()


@pytest.fixture
def client(upstream: FakeUpstream) -> TestClient:
    return build_client(upstream)
