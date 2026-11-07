"""Простой TTL-кэш в памяти процесса.

Сейчас TTL = 5 секунд, чтобы при отладке было видно HIT/MISS.
Позже сюда можно поставить cachetools.TTLCache или Redis — интерфейс
(`get` / `set` / `stats`) менять не придётся.
"""

from __future__ import annotations

from dataclasses import dataclass
from time import monotonic
from typing import Any, Hashable


@dataclass
class _Entry:
    value: Any
    expires_at: float


class TTLCache:
    def __init__(self, ttl_seconds: float) -> None:
        self._ttl = ttl_seconds
        self._data: dict[Hashable, _Entry] = {}
        self.hits = 0
        self.misses = 0

    @property
    def ttl_seconds(self) -> float:
        return self._ttl

    def get(self, key: Hashable) -> Any | None:
        entry = self._data.get(key)
        if entry is None or entry.expires_at <= monotonic():
            self._data.pop(key, None)
            self.misses += 1
            return None
        self.hits += 1
        return entry.value

    def set(self, key: Hashable, value: Any) -> None:
        self._data[key] = _Entry(value, monotonic() + self._ttl)

    def stats(self) -> dict[str, float | int]:
        return {
            "ttl_seconds": self._ttl,
            "size": len(self._data),
            "hits": self.hits,
            "misses": self.misses,
        }
