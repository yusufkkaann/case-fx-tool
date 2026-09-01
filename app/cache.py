from __future__ import annotations

import time
from typing import Callable, Generic, Optional, TypeVar

K = TypeVar("K")
V = TypeVar("V")


class TTLCache(Generic[K, V]):
    """Minimal in-process cache. A ``None`` ttl means the entry never expires,
    which is safe for a rate belonging to a fixed past date."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._store: dict[K, tuple[Optional[float], V]] = {}
        self._clock = clock

    def get(self, key: K) -> Optional[V]:
        item = self._store.get(key)
        if item is None:
            return None
        expires_at, value = item
        if expires_at is not None and self._clock() >= expires_at:
            del self._store[key]
            return None
        return value

    def set(self, key: K, value: V, ttl: Optional[float] = None) -> None:
        expires_at = None if ttl is None else self._clock() + ttl
        self._store[key] = (expires_at, value)
