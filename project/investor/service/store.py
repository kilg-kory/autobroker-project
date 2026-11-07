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

# Сколько ждать первого наполнения ключа, который запросили впервые. Ждём
# фоновый цикл (он просыпается сразу при регистрации ключа), а не идём в API.
FIRST_FILL_WAIT_SECONDS = float(os.getenv("FIRST_FILL_WAIT_SECONDS", "15"))

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
    """Чтение из БД + фоновое наполнение из источника.

    Разделение намеренное: HTTP-запросы только читают PostgreSQL, а в T-Invest
    ходит единственный фоновый цикл. Так один клиент не может спровоцировать
    вызовы биржевого API, а нагрузка на источник не зависит от числа фронтендов.

    Новый ключ (другой инструмент или глубина) регистрируется при первом
    запросе, будит цикл через `_wake` и ждёт первого наполнения — но ждёт именно
    цикл, а не делает собственный запрос.
    """

    storage: CandleStorage
    keys: set[Key] = field(default_factory=set)
    refreshes: int = 0
    errors: int = 0
    last_error: str | None = None
    last_fetched: int = 0
    last_source: str = "-"
    #: чем наполнен ключ: tinvest, mixed, no_token, error (пустой — не наполняли)
    sources: dict[Key, str] = field(default_factory=dict)
    _wake: asyncio.Event = field(default_factory=asyncio.Event)
    _filled: dict[Key, asyncio.Event] = field(default_factory=dict)

    def register(self, key: Key) -> asyncio.Event:
        """Добавляет ключ к фоновому обновлению и возвращает его «готовность»."""
        self._filled.setdefault(key, asyncio.Event())
        if key not in self.keys:
            self.keys.add(key)
            self._wake.set()  # новый ключ — пусть цикл не ждёт следующего тика
        return self._filled[key]

    async def get(self, key: Key) -> tuple[list[dict[str, Any]], str]:
        """Свечи за окно ключа — только из БД. В источник не ходим никогда."""
        filled = self.register(key)
        if key not in self.sources:
            # ключ видит впервые: даём циклу шанс наполнить его прямо сейчас
            try:
                await asyncio.wait_for(filled.wait(), timeout=FIRST_FILL_WAIT_SECONDS)
            except asyncio.TimeoutError:
                logger.warning(
                    "%s/%s: данных ещё нет, фоновый цикл не успел за %.0f с",
                    key[0],
                    key[1],
                    FIRST_FILL_WAIT_SECONDS,
                )

        from_, to = window(key)
        candles = await asyncio.to_thread(self.storage.load, key, from_, to)
        return candles, "postgres"

    async def refresh_key(self, key: Key) -> None:
        """Докачка недостающего и запись в БД — вызывается только циклом."""
        # ключи прогрева не проходили через register(), поэтому событие готовности
        # создаём здесь же, а не полагаемся на словарь
        filled = self._filled.setdefault(key, asyncio.Event())
        from_, to = window(key)
        step = step_for(key[1])

        bounds = await asyncio.to_thread(self.storage.bounds, key)
        ranges = plan_missing(from_, to, bounds, step)

        fetched = 0
        sources: set[str] = set()

        for start, end in ranges:
            try:
                result = await asyncio.to_thread(fetch_range, key[0], key[1], start, end)
            except Exception as exc:  # noqa: BLE001
                self.errors += 1
                self.last_error = f"{type(exc).__name__}: {exc}"
                logger.warning("источник недоступен (%s), остаёмся на том, что в БД", exc)
                sources.add("error")
                continue

            sources.add(result.source)
            if result.candles:
                fetched += await asyncio.to_thread(self.storage.upsert, key, result.candles)

        # "error" — источник не ответил; данные в базе всё равно есть
        sources.discard("error")
        source = (
            "postgres"
            if not sources
            else ("mixed" if len(sources) > 1 else next(iter(sources)))
        )

        self.refreshes += 1
        self.last_fetched = fetched
        self.last_source = source
        self.sources[key] = source
        filled.set()

        candles = await asyncio.to_thread(self.storage.load, key, from_, to)
        logger.info(
            "%s/%s: в БД %d свечей, докачано %d за %d диапазон(ов), источник: %s",
            key[0],
            key[1],
            len(candles),
            fetched,
            len(ranges),
            source,
        )

    async def refresh_all(self) -> None:
        for key in sorted(self.keys | set(WARMUP_KEYS)):
            try:
                await self.refresh_key(key)
            except Exception as exc:  # noqa: BLE001 - один сбой не должен ронять сервис
                self.errors += 1
                self.last_error = f"{type(exc).__name__}: {exc}"
                logger.warning("не удалось обновить %s: %s", key, exc)

    async def run_refresher(self) -> None:
        """Единственный потребитель биржевого API."""
        logger.info(
            "фоновое обновление: каждые %.0f с или сразу после появления нового ключа",
            REFRESH_INTERVAL_SECONDS,
        )
        while True:
            try:
                await asyncio.wait_for(self._wake.wait(), timeout=REFRESH_INTERVAL_SECONDS)
            except asyncio.TimeoutError:
                pass
            self._wake.clear()
            await self.refresh_all()

    async def health(self) -> dict[str, Any]:
        snapshots = {}
        for key in sorted(self.keys | set(WARMUP_KEYS)):
            name = f"{key[0]}/{key[1]}/{key[2]}"
            try:
                snapshots[name] = {
                    "source": self.sources.get(key, "не наполнялся"),
                    **(await asyncio.to_thread(self.storage.stats, key)),
                }
            except Exception as exc:  # noqa: BLE001
                snapshots[name] = {"error": str(exc)}
        return snapshots
