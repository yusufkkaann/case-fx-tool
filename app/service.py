from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Callable, Optional

from .cache import TTLCache
from .errors import ErrorCode, FxError
from .models import ConversionResponse
from .upstream import FrankfurterClient, UpstreamRate

SERIES_START = date(1999, 1, 4)  # first ECB reference rate published
SOURCE = "ECB via frankfurter.dev"
_CENT = Decimal("0.01")
_CURRENCIES_KEY = "__currencies__"
_CURRENCIES_TTL = 24 * 3600


class ConversionService:
    """Validates a request, resolves an honest rate and computes the result.

    The rate that is used always carries the real date it belongs to (from the
    upstream ``date`` field), so a fallback to an earlier business day is always
    visible to the caller instead of being silently mislabelled.
    """

    def __init__(
        self,
        client: FrankfurterClient,
        cache: TTLCache,
        latest_ttl: float,
        today: Callable[[], date] = date.today,
    ) -> None:
        self._client = client
        self._cache = cache
        self._latest_ttl = latest_ttl
        self._today = today

    async def convert(
        self,
        amount: Decimal,
        base: str,
        target: str,
        on: Optional[date],
    ) -> ConversionResponse:
        base = self._normalize_currency(base)
        target = self._normalize_currency(target)
        self._validate_amount(amount)

        if base == target:
            raise FxError(
                ErrorCode.same_currency,
                "'from' and 'to' must be different currencies.",
                400,
            )

        self._validate_date(on)
        await self._ensure_known(base, target)

        rate = await self._resolve_rate(base, target, on)
        result = (amount * rate.rate).quantize(_CENT, rounding=ROUND_HALF_UP)

        return ConversionResponse(
            amount=amount,
            from_=base,
            to=target,
            rate=rate.rate,
            result=result,
            rate_date=rate.rate_date,
            asked_date=on,
            source=SOURCE,
        )

    @staticmethod
    def _normalize_currency(code: str) -> str:
        normalized = code.strip().upper()
        if len(normalized) != 3 or not normalized.isalpha():
            raise FxError(
                ErrorCode.unknown_currency,
                f"'{code}' is not a valid ISO 4217 currency code.",
                400,
            )
        return normalized

    @staticmethod
    def _validate_amount(amount: Decimal) -> None:
        if not amount.is_finite():
            raise FxError(ErrorCode.invalid_amount, "amount must be a finite number.", 400)
        if amount <= 0:
            raise FxError(ErrorCode.invalid_amount, "amount must be greater than zero.", 400)

    def _validate_date(self, on: Optional[date]) -> None:
        if on is None:
            return
        if on > self._today():
            raise FxError(
                ErrorCode.future_date,
                "date is in the future; no exchange rate exists yet.",
                400,
            )
        if on < SERIES_START:
            raise FxError(
                ErrorCode.date_out_of_range,
                f"date is before the published series, which starts on {SERIES_START.isoformat()}.",
                400,
            )

    async def _ensure_known(self, base: str, target: str) -> None:
        currencies = self._cache.get(_CURRENCIES_KEY)
        if currencies is None:
            currencies = await self._client.get_currencies()
            self._cache.set(_CURRENCIES_KEY, currencies, ttl=_CURRENCIES_TTL)
        unknown = {c for c in (base, target) if c not in currencies}
        if unknown:
            raise FxError(
                ErrorCode.unknown_currency,
                f"unknown currency code(s): {', '.join(sorted(unknown))}.",
                400,
            )

    async def _resolve_rate(self, base: str, target: str, on: Optional[date]) -> UpstreamRate:
        key = (base, target, on.isoformat() if on else "latest")
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        rate = await self._client.get_rate(base, target, on)
        # A fixed past date never changes; "latest" moves each business day.
        ttl = None if on is not None else self._latest_ttl
        self._cache.set(key, rate, ttl=ttl)
        return rate
