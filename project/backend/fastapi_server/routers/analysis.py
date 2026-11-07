from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Response

from fastapi_server.cache import TTLCache
from fastapi_server.config import CACHE_TTL_SECONDS
from fastapi_server.investor_client import InvestorUnavailable, fetch_analysis
from fastapi_server.models import AnalysisResponse

DEFAULT_INSTRUMENT = "BBG004730N88"


@dataclass(frozen=True)
class _Payload:
    analysis: AnalysisResponse
    source: str


_cache = TTLCache(CACHE_TTL_SECONDS)

router = APIRouter(prefix="/analysis", tags=["Analysis"])


@router.get("", response_model=AnalysisResponse)
def read_analysis(
    response: Response,
    instrument_id: str = Query(DEFAULT_INSTRUMENT, description="Тикер T-Invest"),
    interval: str = Query("CANDLE_INTERVAL_HOUR", description="CANDLE_INTERVAL_MIN_15 | _HOUR | _DAY"),
    days: int = Query(30, ge=1, le=365, description="Глубина истории в днях"),
) -> AnalysisResponse:
    """Индикаторы и сигналы из investor. Ответ кэшируется на CACHE_TTL_SECONDS.

    Заголовки: X-Cache (HIT/MISS), X-Cache-TTL, X-Data-Source, X-Signals-Count.
    """
    key = (instrument_id, interval, days)
    payload = _cache.get(key)

    if payload is None:
        try:
            fetched = fetch_analysis(
                instrument_id=instrument_id, interval=interval, days=days
            )
        except InvestorUnavailable as exc:
            raise HTTPException(status_code=503, detail=f"investor недоступен: {exc}") from exc

        payload = _Payload(
            analysis=AnalysisResponse(**fetched.analysis),
            source=fetched.source,
        )
        _cache.set(key, payload)
        response.headers["X-Cache"] = "MISS"
    else:
        response.headers["X-Cache"] = "HIT"

    response.headers["X-Cache-TTL"] = str(int(CACHE_TTL_SECONDS))
    response.headers["X-Data-Source"] = payload.source
    response.headers["X-Signals-Count"] = str(len(payload.analysis.signals))
    return payload.analysis


@router.get("/cache/stats")
def read_cache_stats() -> dict[str, Any]:
    """Состояние кэша аналитики."""
    return _cache.stats()
