from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

import httpx

from tests.conftest import FakeUpstream, build_client


def _expected(amount: str, rate: str) -> float:
    return float((Decimal(amount) * Decimal(rate)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def test_happy_path_weekday(client):
    resp = client.get("/tools/convert", params={"amount": 250, "from": "EUR", "to": "TRY", "date": "2026-08-28"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["from"] == "EUR"
    assert body["to"] == "TRY"
    assert body["rate"] == 47.1234
    assert body["result"] == _expected("250", "47.1234")
    assert body["rate_date"] == "2026-08-28"
    assert body["asked_date"] == "2026-08-28"
    assert body["source"] == "ECB via frankfurter.dev"


def test_weekend_fallback_is_visible():
    upstream = FakeUpstream(weekend_map={"2026-08-29": "2026-08-28"})
    client = build_client(upstream)
    resp = client.get("/tools/convert", params={"amount": 100, "from": "EUR", "to": "TRY", "date": "2026-08-29"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["asked_date"] == "2026-08-29"
    assert body["rate_date"] == "2026-08-28"  # the real day the rate belongs to


def test_no_date_uses_latest_and_omits_asked_date(client):
    resp = client.get("/tools/convert", params={"amount": 10, "from": "EUR", "to": "TRY"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["asked_date"] is None
    assert body["rate_date"] == "2026-08-31"


def test_rate_is_not_rounded(client):
    resp = client.get("/tools/convert", params={"amount": 1, "from": "EUR", "to": "TRY", "date": "2026-08-28"})
    assert resp.json()["rate"] == 47.1234  # full precision, not 47.12


def test_future_date_rejected_without_calling_upstream():
    upstream = FakeUpstream()
    client = build_client(upstream, today=date(2026, 8, 31))
    resp = client.get("/tools/convert", params={"amount": 5, "from": "EUR", "to": "TRY", "date": "2027-01-01"})
    assert resp.status_code == 400
    assert resp.json()["error"] == "future_date"
    assert upstream.calls["rate"] == 0
    assert upstream.calls["currencies"] == 0


def test_date_before_series_rejected():
    client = build_client(FakeUpstream())
    resp = client.get("/tools/convert", params={"amount": 5, "from": "EUR", "to": "TRY", "date": "1998-01-01"})
    assert resp.status_code == 400
    assert resp.json()["error"] == "date_out_of_range"


def test_same_currency_rejected(client):
    resp = client.get("/tools/convert", params={"amount": 5, "from": "EUR", "to": "EUR"})
    assert resp.status_code == 400
    assert resp.json()["error"] == "same_currency"


def test_unknown_currency_rejected(client):
    resp = client.get("/tools/convert", params={"amount": 5, "from": "EUR", "to": "XYZ"})
    assert resp.status_code == 400
    assert resp.json()["error"] == "unknown_currency"


def test_malformed_currency_rejected(client):
    resp = client.get("/tools/convert", params={"amount": 5, "from": "EU", "to": "TRY"})
    assert resp.status_code == 400
    assert resp.json()["error"] == "unknown_currency"


def test_zero_amount_rejected(client):
    resp = client.get("/tools/convert", params={"amount": 0, "from": "EUR", "to": "TRY"})
    assert resp.status_code == 400
    assert resp.json()["error"] == "invalid_amount"


def test_negative_amount_rejected(client):
    resp = client.get("/tools/convert", params={"amount": -5, "from": "EUR", "to": "TRY"})
    assert resp.status_code == 400
    assert resp.json()["error"] == "invalid_amount"


def test_missing_amount_rejected(client):
    resp = client.get("/tools/convert", params={"from": "EUR", "to": "TRY"})
    assert resp.status_code == 422
    assert resp.json()["error"] == "invalid_request"


def test_malformed_amount_rejected(client):
    resp = client.get("/tools/convert", params={"amount": "abc", "from": "EUR", "to": "TRY"})
    assert resp.status_code == 422
    assert resp.json()["error"] == "invalid_request"


def test_high_precision_amount_is_accepted(client):
    resp = client.get("/tools/convert", params={"amount": "0.1234567890", "from": "EUR", "to": "TRY", "date": "2026-08-28"})
    assert resp.status_code == 200
    assert resp.json()["result"] == _expected("0.1234567890", "47.1234")


def test_decimal_avoids_float_rounding_error():
    # 2.675 * 1 rounds to 2.68; with binary float, round(2.675, 2) wrongly gives 2.67.
    upstream = FakeUpstream(rate=1)
    client = build_client(upstream)
    resp = client.get("/tools/convert", params={"amount": "2.675", "from": "EUR", "to": "TRY", "date": "2026-08-28"})
    assert resp.status_code == 200
    assert resp.json()["result"] == 2.68


def test_upstream_server_error_maps_to_502():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/currencies":
            return httpx.Response(200, json={"EUR": "Euro", "TRY": "Turkish Lira"})
        return httpx.Response(500, text="upstream is on fire")

    client = build_client(handler)
    resp = client.get("/tools/convert", params={"amount": 5, "from": "EUR", "to": "TRY"})
    assert resp.status_code == 502
    assert resp.json()["error"] == "upstream_unavailable"


def test_upstream_non_json_maps_to_502():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/currencies":
            return httpx.Response(200, json={"EUR": "Euro", "TRY": "Turkish Lira"})
        return httpx.Response(200, text="<html>not json</html>")

    client = build_client(handler)
    resp = client.get("/tools/convert", params={"amount": 5, "from": "EUR", "to": "TRY"})
    assert resp.status_code == 502
    assert resp.json()["error"] == "upstream_invalid_response"


def test_upstream_timeout_maps_to_504():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/currencies":
            return httpx.Response(200, json={"EUR": "Euro", "TRY": "Turkish Lira"})
        raise httpx.ReadTimeout("timed out", request=request)

    client = build_client(handler)
    resp = client.get("/tools/convert", params={"amount": 5, "from": "EUR", "to": "TRY"})
    assert resp.status_code == 504
    assert resp.json()["error"] == "upstream_unavailable"


def test_upstream_missing_rate_maps_to_rate_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/currencies":
            return httpx.Response(200, json={"EUR": "Euro", "TRY": "Turkish Lira"})
        return httpx.Response(200, json={"amount": 1.0, "base": "EUR", "date": "2026-08-28", "rates": {}})

    client = build_client(handler)
    resp = client.get("/tools/convert", params={"amount": 5, "from": "EUR", "to": "TRY", "date": "2026-08-28"})
    assert resp.status_code == 404
    assert resp.json()["error"] == "rate_unavailable"


def test_repeat_request_is_served_from_cache():
    upstream = FakeUpstream()
    client = build_client(upstream)
    params = {"amount": 5, "from": "EUR", "to": "TRY", "date": "2026-08-28"}
    client.get("/tools/convert", params=params)
    client.get("/tools/convert", params=params)
    assert upstream.calls["rate"] == 1  # second request did not hit upstream


def test_error_response_shape(client):
    resp = client.get("/tools/convert", params={"amount": 5, "from": "EUR", "to": "EUR"})
    assert set(resp.json().keys()) == {"error", "message"}


def test_health():
    client = build_client(FakeUpstream())
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
