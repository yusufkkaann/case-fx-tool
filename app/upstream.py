from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Optional

import httpx

from .errors import ErrorCode, FxError


@dataclass(frozen=True)
class UpstreamRate:
    rate: Decimal
    rate_date: date


class FrankfurterClient:
    """Thin async wrapper over the Frankfurter (ECB) HTTP API.

    Every upstream failure is translated into an :class:`FxError` so callers
    never see a raw exception, an unchecked status code or a fabricated number.
    """

    def __init__(self, client: httpx.AsyncClient, base_url: str) -> None:
        self._client = client
        self._base = base_url.rstrip("/")

    async def _get(self, path: str, params: dict) -> dict:
        try:
            response = await self._client.get(f"{self._base}/v1/{path}", params=params)
        except httpx.TimeoutException as exc:
            raise FxError(
                ErrorCode.upstream_unavailable,
                "The rate provider did not respond in time.",
                504,
            ) from exc
        except httpx.RequestError as exc:
            raise FxError(
                ErrorCode.upstream_unavailable,
                "The rate provider could not be reached.",
                502,
            ) from exc

        if response.status_code == 404:
            raise FxError(
                ErrorCode.rate_unavailable,
                "No rate is available for the requested currencies or date.",
                404,
            )
        if response.status_code >= 400:
            raise FxError(
                ErrorCode.upstream_unavailable,
                "The rate provider returned an error.",
                502,
            )

        try:
            # Parse numbers as Decimal so a rate never passes through float.
            data = json.loads(response.text, parse_float=Decimal)
        except ValueError as exc:
            raise FxError(
                ErrorCode.upstream_invalid_response,
                "The rate provider returned a malformed response.",
                502,
            ) from exc

        if not isinstance(data, dict):
            raise FxError(
                ErrorCode.upstream_invalid_response,
                "The rate provider returned a malformed response.",
                502,
            )
        return data

    async def get_currencies(self) -> set[str]:
        data = await self._get("currencies", {})
        return {code.upper() for code in data}

    async def get_rate(self, base: str, target: str, on: Optional[date]) -> UpstreamRate:
        path = on.isoformat() if on else "latest"
        data = await self._get(path, {"base": base, "symbols": target})

        rates = data.get("rates")
        rate_date_raw = data.get("date")
        if not isinstance(rates, dict) or target not in rates or rate_date_raw is None:
            raise FxError(
                ErrorCode.rate_unavailable,
                "No rate is available for the requested currencies or date.",
                404,
            )

        try:
            rate_value = Decimal(str(rates[target]))
            rate_date = date.fromisoformat(str(rate_date_raw))
        except (TypeError, ValueError, InvalidOperation) as exc:
            raise FxError(
                ErrorCode.upstream_invalid_response,
                "The rate provider returned a malformed response.",
                502,
            ) from exc

        return UpstreamRate(rate=rate_value, rate_date=rate_date)
