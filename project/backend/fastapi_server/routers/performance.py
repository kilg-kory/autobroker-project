from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Response

from fastapi_server.cache import TTLCache
from fastapi_server.config import CACHE_TTL_SECONDS
from fastapi_server.investor_client import InvestorUnavailable, fetch_performance
from fastapi_server.models import PerformanceResponse

DEFAULT_INSTRUMENT = "BBG004730N88"


@dataclass(frozen=True)
class _Payload:
    performance: PerformanceResponse
    source: str


_cache = TTLCache(CACHE_TTL_SECONDS)

router = APIRouter(prefix="/performance", tags=["Performance"])


def _parse_patterns(patterns: str | None) -> list[str]:
    """`a,b,c` -> ['a', 'b', 'c']; пустая строка и пробелы отбрасываются."""
    if not patterns:
        return []
    return [item.strip() for item in patterns.split(",") if item.strip()]


@router.get("", response_model=PerformanceResponse)
def read_performance(
    response: Response,
    instrument_id: str = Query(DEFAULT_INSTRUMENT, description="Тикер T-Invest"),
    interval: str = Query("CANDLE_INTERVAL_HOUR", description="CANDLE_INTERVAL_MIN_15 | _HOUR | _DAY"),
    days: int = Query(30, ge=1, le=365, description="Глубина истории в днях"),
    patterns: str | None = Query(
        None,
        description="id паттернов через запятую; не задано — все паттерны окна",
    ),
) -> PerformanceResponse:
    """Бэктест сигналов из investor. Ответ кэшируется на CACHE_TTL_SECONDS.

    Ключ кэша включает список паттернов: пересчёт с другим набором сигналов —
    это другой ответ, и старый кэш ему не мешает.

    Заголовки: X-Cache (HIT/MISS), X-Cache-TTL, X-Data-Source,
    X-Patterns-Count, X-Trades-Count.
    """
    selected = _parse_patterns(patterns)
    explicit = patterns is not None
    key = (instrument_id, interval, days, tuple(sorted(selected)) if explicit else None)
    payload = _cache.get(key)

    if payload is None:
        try:
            fetched = fetch_performance(
                instrument_id=instrument_id,
                interval=interval,
                days=days,
                patterns=selected if explicit else None,
            )
        except InvestorUnavailable as exc:
            raise HTTPException(status_code=503, detail=f"investor недоступен: {exc}") from exc

        payload = _Payload(
            performance=PerformanceResponse(**fetched.performance),
            source=fetched.source,
        )
        _cache.set(key, payload)
        response.headers["X-Cache"] = "MISS"
    else:
        response.headers["X-Cache"] = "HIT"

    response.headers["X-Cache-TTL"] = str(int(CACHE_TTL_SECONDS))
    response.headers["X-Data-Source"] = payload.source
    response.headers["X-Patterns-Count"] = str(payload.performance.total.patterns)
    response.headers["X-Trades-Count"] = str(payload.performance.total.trades)
    return payload.performance


@router.get("/cache/stats")
def read_cache_stats() -> dict[str, Any]:
    """Состояние кэша бэктеста."""
    return _cache.stats()
