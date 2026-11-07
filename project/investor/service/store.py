"""Свечи: читаем из PostgreSQL, у источника докачиваем только недостающее.

Логика простая и работает по границам сохранённого:

    [from_ ............ to]
    [stored_min ... stored_max]

    недостающее = (from_ .. stored_min - шаг) + (stored_max .. to)

Второй диапазон включает последний сохранённый бар: он мог ещё не закрыться,
поэтому его перечитываем и обновляем через upsert. Всё, что уже есть в базе,
повторно не запрашивается.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from market.candles import DEFAULT_INSTRUMENT, align, fetch_range, step_for
from service.storage import CandleStorage

logger = logging.getLogger("investor.service")

REFRESH_INTERVAL_SECONDS = float(os.getenv("REFRESH_INTERVAL_SECONDS", "30"))
WARMUP_DAYS = int(os.getenv("WARMUP_DAYS", "30"))

Key = tuple[str, str, int]


def _csv_env(name: str, default: str) -> list[str]:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


WARMUP_INSTRUMENTS = _csv_env("WARMUP_INSTRUMENTS", DEFAULT_INSTRUMENT)
WARMUP_INTERVALS = _csv_env("WARMUP_INTERVALS", "CANDLE_INTERVAL_HOUR")
WARMUP_KEYS: list[Key] = [
    (instrument, interval, WARMUP_DAYS)
    for instrument in WARMUP_INSTRUMENTS
    for interval in WARMUP_INTERVALS
]


def window(key: Key, now: datetime | None = None) -> tuple[datetime, datetime]:
    """Запрошенное окно: от `to - days` до текущего (выровненного) момента."""
    _, interval, days = key
    to = align(now or datetime.now(timezone.utc), step_for(interval))
    return to - timedelta(days=days), to


def plan_missing(
    from_: datetime,
    to: datetime,
    bounds: tuple[datetime, datetime] | None,
    step: timedelta,
) -> list[tuple[datetime, datetime]]:
    """Какие диапазоны нужно докачать, чтобы покрыть [from_, to]."""
    if bounds is None:
        return [(from_, to)]

    stored_min, stored_max = bounds
    ranges: list[tuple[datetime, datetime]] = []

    # начало окна лежит раньше сохранённого: докачиваем, только если дыра
    # больше одного шага — иначе получится запрос за единственный бар,
    # которого в источнике может и не быть (ночь, выходной)
    if from_ < stored_min:
        gap_end = stored_min - step
        if gap_end >= from_ + step:
            ranges.append((from_, gap_end))

    # последний бар мог не закрыться — перечитываем его вместе с хвостом
    ranges.append((stored_max, max(to, stored_max)))

    return [item for item in ranges if item[0] <= item[1]]


@dataclass
class Store:
    storage: CandleStorage
    keys: set[Key] = field(default_factory=set)
    refreshes: int = 0
    errors: int = 0
    last_error: str | None = None
    last_fetched: int = 0
    last_source: str = "-"

    async def get(self, key: Key) -> tuple[list[dict[str, Any]], str]:
        """Свечи за окно ключа. Возвращает данные и то, откуда они взялись."""
        self.keys.add(key)
        from_, to = window(key)
        step = step_for(key[1])

        bounds = await asyncio.to_thread(self.storage.bounds, key)
        ranges = plan_missing(from_, to, bounds, step)

        fetched = 0
        sources: set[str] = set()

        for start, end in ranges:
            try:
                result = await asyncio.to_thread(
                    fetch_range, key[0], key[1], start, end
                )
            except Exception as exc:  # noqa: BLE001
                self.errors += 1
                self.last_error = f"{type(exc).__name__}: {exc}"
                logger.warning("источник недоступен (%s), отдаём то, что в БД", exc)
                continue

            sources.add(result.source)
            if result.candles:
                fetched += await asyncio.to_thread(self.storage.upsert, key, result.candles)

        candles = await asyncio.to_thread(self.storage.load, key, from_, to)

        self.refreshes += 1
        self.last_fetched = fetched
        # "error" — источник не ответил; данные всё равно взяты из базы
        sources.discard("error")
        source = (
            "postgres"
            if not sources
            else ("mixed" if len(sources) > 1 else next(iter(sources)))
        )
        self.last_source = source
        logger.info(
            "%s/%s: в БД %d свечей, докачано %d за %d диапазон(ов), ответ: %s",
            key[0],
            key[1],
            len(candles),
            fetched,
            len(ranges),
            source,
        )
        return candles, source

    async def refresh_all(self) -> None:
        for key in sorted(self.keys | set(WARMUP_KEYS)):
            try:
                await self.get(key)
            except Exception as exc:  # noqa: BLE001 - один сбой не должен ронять сервис
                self.errors += 1
                self.last_error = f"{type(exc).__name__}: {exc}"
                logger.warning("не удалось обновить %s: %s", key, exc)

    async def run_refresher(self) -> None:
        logger.info("фоновое обновление каждые %.0f с", REFRESH_INTERVAL_SECONDS)
        while True:
            await asyncio.sleep(REFRESH_INTERVAL_SECONDS)
            await self.refresh_all()

    async def health(self) -> dict[str, Any]:
        snapshots = {}
        for key in sorted(self.keys | set(WARMUP_KEYS)):
            try:
                snapshots[f"{key[0]}/{key[1]}/{key[2]}"] = await asyncio.to_thread(
                    self.storage.stats, key
                )
            except Exception as exc:  # noqa: BLE001
                snapshots[f"{key[0]}/{key[1]}/{key[2]}"] = {"error": str(exc)}
        return snapshots
