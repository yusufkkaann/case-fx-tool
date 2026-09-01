from __future__ import annotations

from enum import Enum


class ErrorCode(str, Enum):
    invalid_request = "invalid_request"
    invalid_amount = "invalid_amount"
    same_currency = "same_currency"
    unknown_currency = "unknown_currency"
    future_date = "future_date"
    date_out_of_range = "date_out_of_range"
    rate_unavailable = "rate_unavailable"
    upstream_unavailable = "upstream_unavailable"
    upstream_invalid_response = "upstream_invalid_response"


class FxError(Exception):
    """Domain error carrying a machine code, a human message and an HTTP status."""

    def __init__(self, code: ErrorCode, message: str, http_status: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status
