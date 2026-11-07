"""HTTP-сервис investor.

Отдельный процесс: хранит свечи в PostgreSQL, докачивает у источника только
недостающие интервалы и обновляет данные по расписанию — независимо от того,
подключён ли кто-то. Ни о каком backend не знает.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Response

from market.candles import DEFAULT_INSTRUMENT
from service import analysis, performance
from service.storage import DATABASE_URL, CandleStorage
from service.store import REFRESH_INTERVAL_SECONDS, WARMUP_KEYS, Store

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("investor.service")

DB_RETRY_ATTEMPTS = 10
DB_RETRY_DELAY_SECONDS = 2.0

_store: Store | None = None


async def _init_storage() -> CandleStorage:
    """Postgres в compose поднимается параллельно — ждём его с повторами."""
    storage = CandleStorage(DATABASE_URL)
    for attempt in range(1, DB_RETRY_ATTEMPTS + 1):
        try:
            await asyncio.to_thread(storage.ensure_schema)
            return storage
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Postgres недоступен (%s), попытка %d/%d",
                exc,
                attempt,
                DB_RETRY_ATTEMPTS,
            )
            await asyncio.sleep(DB_RETRY_DELAY_SECONDS)
    raise RuntimeError("не удалось подключиться к Postgres")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global _store

    storage = await _init_storage()
    _store = Store(storage=storage)
    await _store.refresh_all()

    refresher = asyncio.create_task(_store.run_refresher())
    try:
        yield
    finally:
        refresher.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await refresher


app = FastAPI(
    title="Investor service",
    description="Свечи из T-Invest API, хранение в PostgreSQL, докачка недостающего",
    version="0.2.0",
    lifespan=lifespan,
)


def _get_store() -> Store:
    if _store is None:
        raise HTTPException(status_code=503, detail="сервис ещё инициализируется")
    return _store


@app.get("/health")
async def health() -> dict[str, object]:
    """Состояние сервиса и содержимого базы."""
    store = _get_store()
    return {
        "status": "ok",
        "refresh_interval_seconds": REFRESH_INTERVAL_SECONDS,
        "refreshes": store.refreshes,
        "errors": store.errors,
        "last_error": store.last_error,
        "last_fetched": store.last_fetched,
        "last_source": store.last_source,
        "keys": sorted(f"{key[0]}/{key[1]}/{key[2]}" for key in store.keys | set(WARMUP_KEYS)),
        "snapshots": await store.health(),
    }


@app.get("/candles")
async def read_candles(
    response: Response,
    instrument_id: str = Query(DEFAULT_INSTRUMENT, description="Тикер T-Invest"),
    interval: str = Query("CANDLE_INTERVAL_HOUR", description="CANDLE_INTERVAL_MIN_15 | _HOUR | _DAY"),
    days: int = Query(30, ge=1, le=365, description="Глубина истории в днях"),
) -> list[dict]:
    """Свечи за окно. Из базы, у источника — только недостающее."""
    store = _get_store()
    try:
        candles, source = await store.get((instrument_id, interval, days))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"нет данных: {exc}") from exc

    response.headers["X-Data-Source"] = source
    response.headers["X-Candles-Count"] = str(len(candles))
    return candles


@app.get("/analysis")
async def read_analysis(
    response: Response,
    instrument_id: str = Query(DEFAULT_INSTRUMENT, description="Тикер T-Invest"),
    interval: str = Query("CANDLE_INTERVAL_HOUR", description="CANDLE_INTERVAL_MIN_15 | _HOUR | _DAY"),
    days: int = Query(30, ge=1, le=365, description="Глубина истории в днях"),
) -> dict:
    """Индикаторы и сигналы по тем же свечам, что отдаёт /candles.

    Индикаторы (SMA/EMA/RSI/ATR) и разметка паттернов считаются здесь, чтобы
    правило было одно для UI, будущего автоброкера и бэктеста. У T-Invest
    ничего дополнительно не запрашивается — только то, что уже в базе.
    """
    store = _get_store()
    try:
        candles, source = await store.get((instrument_id, interval, days))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"нет данных: {exc}") from exc

    # расчёт на numpy/python — уводим из event loop, чтобы не тормозить HTTP
    result = await asyncio.to_thread(
        analysis.analyze, candles, instrument_id, interval, days, source
    )

    response.headers["X-Data-Source"] = source
    response.headers["X-Signals-Count"] = str(len(result["signals"]))
    return result


@app.get("/performance")
async def read_performance(
    response: Response,
    instrument_id: str = Query(DEFAULT_INSTRUMENT, description="Тикер T-Invest"),
    interval: str = Query("CANDLE_INTERVAL_HOUR", description="CANDLE_INTERVAL_MIN_15 | _HOUR | _DAY"),
    days: int = Query(30, ge=1, le=365, description="Глубина истории в днях"),
    patterns: str | None = Query(
        None,
        description="id паттернов через запятую; не задано — все паттерны окна",
    ),
) -> dict:
    """Бэктест сигналов: hit ratio, profit factor, risk/reward, число сделок.

    Правила — из учебного примера (архив: learning/investor_book/util/performance.py):
    вход по открытию бара сигнала, выход по открытию следующего сигнала того же
    паттерна, без комиссий и стопов.
    `patterns` позволяет считать только выбранные паттерны — пересчёт с
    включёнными и выключенными сигналами делает клиент.
    """
    store = _get_store()
    try:
        candles, source = await store.get((instrument_id, interval, days))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"нет данных: {exc}") from exc

    selected = (
        [item.strip() for item in patterns.split(",") if item.strip()]
        if patterns is not None
        else None
    )

    result = await asyncio.to_thread(performance.evaluate, candles, selected)

    response.headers["X-Data-Source"] = source
    response.headers["X-Patterns-Count"] = str(result["total"]["patterns"])
    response.headers["X-Trades-Count"] = str(result["total"]["trades"])
    return {
        "instrument_id": instrument_id,
        "interval": interval,
        "days": days,
        "candles": len(candles),
        "source": source,
        **result,
    }
