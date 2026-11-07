"""HTTP-клиент сервиса investor.

Backend не импортирует код investor и ничего не знает о его устройстве:
только URL из окружения и JSON-контракт `HistoricCandle`.

Прокси из окружения намеренно отключён (`trust_env=False`): httpx иначе
подхватывает системный прокси (в Windows — из реестра WinINET) и отправляет
туда даже запросы к внутреннему адресу. При необходимости включается
переменной INVESTOR_TRUST_ENV=1.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from fastapi_server.config import (
    INVESTOR_API_URL,
    INVESTOR_TIMEOUT_SECONDS,
    INVESTOR_TRUST_ENV,
)

_client = httpx.Client(
    base_url=INVESTOR_API_URL,
    timeout=INVESTOR_TIMEOUT_SECONDS,
    trust_env=INVESTOR_TRUST_ENV,
)


class InvestorUnavailable(RuntimeError):
    """Сервис недоступен, ответил ошибкой или не ответил вовремя."""


@dataclass(frozen=True)
class CandlesResponse:
    candles: list[dict[str, Any]]
    source: str


@dataclass(frozen=True)
class AnalysisResult:
    """Аналитика приходит как готовый JSON: backend её не пересчитывает."""

    analysis: dict[str, Any]
    source: str


@dataclass(frozen=True)
class PerformanceResult:
    """Бэктест тоже считается в investor — здесь только транспорт."""

    performance: dict[str, Any]
    source: str


def fetch_candles(instrument_id: str, interval: str, days: int) -> CandlesResponse:
    try:
        response = _client.get(
            "/candles",
            params={"instrument_id": instrument_id, "interval": interval, "days": days},
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise InvestorUnavailable(f"{INVESTOR_API_URL}: {exc}") from exc

    return CandlesResponse(
        candles=response.json(),
        source=response.headers.get("X-Data-Source", "unknown"),
    )


def fetch_analysis(instrument_id: str, interval: str, days: int) -> AnalysisResult:
    try:
        response = _client.get(
            "/analysis",
            params={"instrument_id": instrument_id, "interval": interval, "days": days},
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise InvestorUnavailable(f"{INVESTOR_API_URL}: {exc}") from exc

    return AnalysisResult(
        analysis=response.json(),
        source=response.headers.get("X-Data-Source", "unknown"),
    )


def fetch_performance(
    instrument_id: str,
    interval: str,
    days: int,
    patterns: list[str] | None,
) -> PerformanceResult:
    params: dict[str, Any] = {
        "instrument_id": instrument_id,
        "interval": interval,
        "days": days,
    }
    if patterns is not None:
        # пустой список отправляем как `patterns=`: так investor отличает
        # «ничего не выбрано» от «параметр не задан — считай все паттерны»
        params["patterns"] = ",".join(patterns)

    try:
        response = _client.get("/performance", params=params)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise InvestorUnavailable(f"{INVESTOR_API_URL}: {exc}") from exc

    return PerformanceResult(
        performance=response.json(),
        source=response.headers.get("X-Data-Source", "unknown"),
    )
