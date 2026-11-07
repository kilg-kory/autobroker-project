"""Источник свечей — только T-Invest API. Моков нет.

Модуль умеет ровно одно: отдать свечи за интервал [from_, to]. Про базу и
про то, что уже сохранено, он не знает — это забота service/store.py.

Если токена нет или API не ответил, возвращается пустой результат: сервис
отдаёт то, что уже лежит в PostgreSQL, а синтетику в реальные данные не
подставляет. Для тестов данные можно загрузить в базу вручную.

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
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
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

# Таймаут одного gRPC-вызова к T-Invest. Ставится интерсептором SDK на сам
# вызов, поэтому SDK действительно прерывает запрос по deadline.
# Значение большое намеренно: история за длинный период выкачивается страницами,
# и каждая страница — отдельный unary-вызов, который может идти долго.
TINVEST_TIMEOUT_SECONDS = float(os.getenv("TINVEST_TIMEOUT_SECONDS", "120"))

STEP_BY_INTERVAL = {
    "CANDLE_INTERVAL_MIN_15": timedelta(minutes=15),
    "CANDLE_INTERVAL_HOUR": timedelta(hours=1),
    "CANDLE_INTERVAL_DAY": timedelta(days=1),
}


@dataclass(frozen=True)
class CandlesResult:
    candles: list[dict[str, Any]]
    source: str  # "tinvest" | "no_token" | "error"


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
    """Свечи за [from_, to] из T-Invest.

    Пустой результат — нормальный ответ: нет токена или API не ответил, значит
    новых данных нет. Синтетику не подставляем, сервис отдаст то, что уже
    лежит в PostgreSQL.

    Таймаут живёт в интерсепторе клиента SDK (`TINVEST_TIMEOUT_SECONDS`),
    а не вокруг вызова: gRPC по deadline сам отменяет запрос, поэтому
    зависший вызов не держит ни поток, ни HTTP-запрос.
    """
    token = os.getenv("TOKEN")
    if not token:
        logger.warning("investor: TOKEN не задан, свечи не запрашиваются")
        return CandlesResult([], "no_token")

    try:
        candles = _from_tinvest(token, instrument_id, interval, from_, to)
    except Exception as exc:  # noqa: BLE001 - ошибка API не должна ломать выдачу
        logger.warning(
            "investor: T-Invest недоступен (%s: %s)", type(exc).__name__, exc
        )
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
    from t_tech.invest.grpc.utils.interceptors import DefaultTimeoutInterceptor
    from t_tech.invest.schemas import CandleSource

    interval_enum = getattr(CandleInterval, interval, CandleInterval.CANDLE_INTERVAL_HOUR)

    # Штатный интерсептор SDK: проставляет deadline каждому unary-вызову.
    # Альтернатива — свой ThreadPoolExecutor с future.result(timeout=...), но
    # она не работает: выход из `with ThreadPoolExecutor(...)` ждёт поток, и
    # зависший вызов всё равно держит запрос до конца.
    timeout = DefaultTimeoutInterceptor(
        unary_timeout=TINVEST_TIMEOUT_SECONDS,
        stream_timeout=None,  # стримов у нас нет
    )

    with Client(token, interceptors=[timeout]) as client:
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
