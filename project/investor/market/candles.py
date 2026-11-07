"""Источник свечей: T-Invest API, при недоступности — детерминированный мок.

Модуль умеет ровно одно: отдать свечи за интервал [from_, to]. Про базу и
про то, что уже сохранено, он не знает — это забота service/store.py.

Формат — HistoricCandle из t_tech.invest:

    {
      "open": {"units": 300, "nano": 0}, "high": ..., "low": ..., "close": ...,
      "volume": 53000,
      "time": "2026-11-06T14:00:00+00:00",
      "isComplete": True,
    }

Ключи в camelCase намеренно: ответ уходит в REST как есть и должен совпадать
с типами фронтенда (src/api/types.ts).
"""

from __future__ import annotations

import logging
import math
import os
import random
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


def _find_env_file() -> Path | None:
    """Ищем .env вверх по дереву: локально это корень репозитория,
    в контейнере файла может не быть — тогда настройки берутся из окружения."""
    for parent in Path(__file__).resolve().parents:
        candidate = parent / ".env"
        if candidate.is_file():
            return candidate
    return None


_ENV_FILE = _find_env_file()
if _ENV_FILE is not None:
    load_dotenv(_ENV_FILE)

DEFAULT_INSTRUMENT = "BBG004730N88"  # Сбербанк, как в tryTAPI.ipynb
NANO = 1_000_000_000
FETCH_TIMEOUT_SECONDS = 10
MAX_CANDLES = 5_000

STEP_BY_INTERVAL = {
    "CANDLE_INTERVAL_MIN_15": timedelta(minutes=15),
    "CANDLE_INTERVAL_HOUR": timedelta(hours=1),
    "CANDLE_INTERVAL_DAY": timedelta(days=1),
}


@dataclass(frozen=True)
class CandlesResult:
    candles: list[dict[str, Any]]
    source: str  # "tinvest" | "mock"


def step_for(interval: str) -> timedelta:
    return STEP_BY_INTERVAL.get(interval, timedelta(hours=1))


def align(moment: datetime, step: timedelta) -> datetime:
    """Округляет время вниз до границы шага (час, 15 минут, сутки)."""
    if step >= timedelta(days=1):
        return moment.replace(hour=0, minute=0, second=0, microsecond=0)
    minutes = int(step.total_seconds() // 60)
    moment = moment.replace(second=0, microsecond=0)
    return moment - timedelta(minutes=moment.minute % minutes)


def fetch_range(
    instrument_id: str,
    interval: str,
    from_: datetime,
    to: datetime,
) -> CandlesResult:
    """Свечи за [from_, to].

    Мок используется только если токена нет вовсе (локальная разработка).
    Если токен есть, но API ответил ошибкой — возвращаем пустой результат:
    подставлять синтетику в реальные данные нельзя, а то, что уже в базе,
    сервис отдаст и так.
    """
    token = os.getenv("TOKEN")
    if not token:
        logger.info("investor: TOKEN не задан, отдаю мок")
        return CandlesResult(_mock_range(interval, from_, to), "mock")

    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(_from_tinvest, token, instrument_id, interval, from_, to)
            candles = future.result(timeout=FETCH_TIMEOUT_SECONDS)
    except FutureTimeout:
        logger.warning("investor: T-Invest не ответил за %d с", FETCH_TIMEOUT_SECONDS)
        return CandlesResult([], "error")
    except Exception as exc:  # noqa: BLE001 - ошибка API не должна ломать выдачу
        logger.warning("investor: T-Invest недоступен (%s: %s)", type(exc).__name__, exc)
        return CandlesResult([], "error")

    logger.info(
        "investor: %d свечей из T-Invest за %s..%s",
        len(candles),
        from_.isoformat(timespec="minutes"),
        to.isoformat(timespec="minutes"),
    )
    return CandlesResult(candles, "tinvest")


def _from_tinvest(
    token: str,
    instrument_id: str,
    interval: str,
    from_: datetime,
    to: datetime,
) -> list[dict[str, Any]]:
    from t_tech.invest import CandleInterval, Client
    from t_tech.invest.schemas import CandleSource

    interval_enum = getattr(CandleInterval, interval, CandleInterval.CANDLE_INTERVAL_HOUR)

    with Client(token) as client:
        raw = client.get_all_candles(
            instrument_id=instrument_id,
            from_=from_,
            to=to,
            interval=interval_enum,
            candle_source_type=CandleSource.CANDLE_SOURCE_UNSPECIFIED,
        )
        return [
            {
                "open": _quotation_of(candle.open),
                "high": _quotation_of(candle.high),
                "low": _quotation_of(candle.low),
                "close": _quotation_of(candle.close),
                "volume": int(candle.volume),
                "time": candle.time,
                "isComplete": bool(candle.is_complete),
            }
            for candle in raw
        ]


def _quotation_of(value: Any) -> dict[str, int]:
    return {"units": int(value.units), "nano": int(value.nano)}


def _to_quotation(price: float) -> dict[str, int]:
    units = int(price)
    return {"units": units, "nano": round((price - units) * NANO)}


def _is_trading_hour(moment: datetime, step: timedelta) -> bool:
    """Основная сессия MOEX: будни 10:00–18:59 MSK (07:00–15:59 UTC)."""
    if step >= timedelta(days=1):
        return True
    return 1 <= moment.isoweekday() <= 5 and 7 <= moment.hour <= 14


def _mock_candle(moment: datetime) -> dict[str, Any]:
    """Детерминированная свеча: зависит только от времени, поэтому диапазоны
    можно запрашивать по частям и получать согласованный ряд."""
    stamp = int(moment.timestamp())
    rng = random.Random(stamp)
    price = 300 + 20 * math.sin(stamp / 86_400 * 0.7)
    open_price = price * (1 + (rng.random() - 0.5) * 0.002)
    close_price = price
    wick = price * (0.0005 + rng.random() * 0.0015)
    high_price = max(open_price, close_price) + wick * rng.random()
    low_price = min(open_price, close_price) - wick * rng.random()
    volume = round(5_000 + rng.random() * 95_000)

    return {
        "open": _to_quotation(open_price),
        "high": _to_quotation(high_price),
        "low": _to_quotation(low_price),
        "close": _to_quotation(close_price),
        "volume": volume,
        "time": moment,
        "isComplete": True,
    }


def _mock_range(interval: str, from_: datetime, to: datetime) -> list[dict[str, Any]]:
    step = step_for(interval)
    cursor = align(from_, step)
    candles: list[dict[str, Any]] = []
    while cursor <= to and len(candles) < MAX_CANDLES:
        if _is_trading_hour(cursor, step):
            candles.append(_mock_candle(cursor))
        cursor += step
    return candles
