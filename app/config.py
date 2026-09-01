from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    """Runtime configuration, read once from the environment."""

    upstream_base: str
    port: int
    request_timeout: float
    latest_cache_ttl: float


@lru_cache
def get_settings() -> Settings:
    return Settings(
        upstream_base=os.environ.get("FX_UPSTREAM_BASE", "https://api.frankfurter.dev").rstrip("/"),
        port=int(os.environ.get("PORT", "8080")),
        request_timeout=float(os.environ.get("FX_REQUEST_TIMEOUT", "5.0")),
        latest_cache_ttl=float(os.environ.get("FX_LATEST_CACHE_TTL", "3600")),
    )
