from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class ConversionResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    amount: Decimal
    from_: str = Field(serialization_alias="from")
    to: str
    rate: Decimal
    result: Decimal
    rate_date: date
    asked_date: date | None
    source: str

    @field_serializer("amount", "rate", "result")
    def _serialize_money(self, value: Decimal) -> float:
        # Money is computed in Decimal; emit JSON numbers to keep the contract.
        return float(value)
