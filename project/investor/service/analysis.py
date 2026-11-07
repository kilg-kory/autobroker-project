"""Аналитика по свечам: индикаторы и распознавание паттернов.

Считается поверх свечей, которые investor уже держит в PostgreSQL: источник
(T-Invest) ради этого повторно не опрашивается.

Почему расчёт на сервере, а не в браузере: правило должно быть одно для всех
потребителей — UI, будущего автоброкера и бэктеста. Фронтенд получает уже
готовые ряды и только рисует их.

Паттерны — модули `signals/*` из песочницы. Каждый принимает матрицу
`[open, high, low, close, buy, sell, atr]` и помечает строки: `1` в колонке
buy — покупка, `-1` в колонке sell — продажа. Движок даёт им общую матрицу и
собирает отметки в один плоский список.

Важное соглашение песочницы: сигнал ставится на **следующий** бар после
подтверждения (`data[i + 1, ...]`), то есть вход — по открытию этого бара.
Поэтому `time` сигнала — бар входа, а `price` — его цена открытия.
"""

from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass
from typing import Any

import numpy as np

logger = logging.getLogger("investor.analysis")

# Раскладка матрицы, общая для всех паттернов песочницы.
OPEN, HIGH, LOW, CLOSE, BUY, SELL, ATR = range(7)
MATRIX_COLUMNS = 7

NANO = 1_000_000_000


def to_float(quotation: dict[str, Any] | float | int) -> float:
    """Quotation {units, nano} -> float. Плоские числа пропускаются как есть."""
    if isinstance(quotation, dict):
        return float(quotation.get("units", 0)) + float(quotation.get("nano", 0)) / NANO
    return float(quotation)


# --------------------------------------------------------------------------
# Индикаторы
# --------------------------------------------------------------------------


def sma(values: list[float], period: int) -> list[float | None]:
    """Простое скользящее среднее; первые `period - 1` точек — None."""
    result: list[float | None] = [None] * len(values)
    if period <= 0:
        return result
    window = 0.0
    for index, value in enumerate(values):
        window += value
        if index >= period:
            window -= values[index - period]
        if index >= period - 1:
            result[index] = window / period
    return result


def ema(values: list[float], period: int) -> list[float | None]:
    """Экспоненциальная средняя; стартует с SMA за первый период."""
    result: list[float | None] = [None] * len(values)
    if period <= 0 or len(values) < period:
        return result
    alpha = 2 / (period + 1)
    seed = sum(values[:period]) / period
    result[period - 1] = seed
    previous = seed
    for index in range(period, len(values)):
        previous = values[index] * alpha + previous * (1 - alpha)
        result[index] = previous
    return result


def rsi(values: list[float], period: int = 14) -> list[float | None]:
    """RSI по Уайлдеру (сглаживание средних приростов и падений)."""
    result: list[float | None] = [None] * len(values)
    if period <= 0 or len(values) <= period:
        return result

    gains = 0.0
    losses = 0.0
    for index in range(1, period + 1):
        delta = values[index] - values[index - 1]
        gains += max(delta, 0.0)
        losses += max(-delta, 0.0)
    average_gain = gains / period
    average_loss = losses / period
    result[period] = _rsi_value(average_gain, average_loss)

    for index in range(period + 1, len(values)):
        delta = values[index] - values[index - 1]
        average_gain = (average_gain * (period - 1) + max(delta, 0.0)) / period
        average_loss = (average_loss * (period - 1) + max(-delta, 0.0)) / period
        result[index] = _rsi_value(average_gain, average_loss)
    return result


def _rsi_value(average_gain: float, average_loss: float) -> float:
    if average_loss == 0:
        return 100.0 if average_gain > 0 else 50.0
    strength = average_gain / average_loss
    return 100 - 100 / (1 + strength)


def atr(
    high: list[float],
    low: list[float],
    close: list[float],
    period: int = 14,
) -> list[float | None]:
    """ATR по Уайлдеру: истинный диапазон, сглаженный как в RSI."""
    result: list[float | None] = [None] * len(close)
    if period <= 0 or len(close) <= period:
        return result

    true_ranges: list[float] = [high[0] - low[0]]
    for index in range(1, len(close)):
        previous_close = close[index - 1]
        true_ranges.append(
            max(
                high[index] - low[index],
                abs(high[index] - previous_close),
                abs(low[index] - previous_close),
            )
        )

    average = sum(true_ranges[:period]) / period
    result[period - 1] = average
    for index in range(period, len(close)):
        average = (average * (period - 1) + true_ranges[index]) / period
        result[index] = average
    return result


INDICATORS: tuple[tuple[str, str, str, int], ...] = (
    # id, заголовок, панель графика, период
    ("sma20", "SMA 20", "price", 20),
    ("ema50", "EMA 50", "price", 50),
    ("rsi14", "RSI 14", "rsi", 14),
    ("atr14", "ATR 14", "atr", 14),
)


# --------------------------------------------------------------------------
# Паттерны
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Pattern:
    """Описание модуля из `signals/`: что вызвать и как читать результат."""

    id: str
    title: str
    module: str
    function: str
    # ohlc — (open, high, low, close, buy, sell)
    # oc   — (open, close, buy, sell)
    # atr  — (open, high, low, close, atr, buy, sell)
    # self — функция сама знает колонки: (data)
    args: str = "ohlc"


PATTERNS: tuple[Pattern, ...] = (
    Pattern("abandoned_baby", "Брошенный младенец", "signals.abandoned_baby", "signal"),
    Pattern("base_signal", "Базовая альфа", "signals.base_signal", "signal", "self"),
    Pattern("blockade", "Блокада", "signals.blockade", "signal"),
    Pattern("bottle", "Бутылка", "signals.bottle", "signal"),
    Pattern("doji", "Доджи", "signals.doji", "signal", "oc"),
    Pattern("doppelganger", "Двойник", "signals.doppelganger", "signal"),
    Pattern("double_trouble", "Двойная неприятность", "signals.double_trouble", "signal", "atr"),
    Pattern("engulfing", "Поглощение", "signals.engulfing", "signal", "oc"),
    Pattern("hammer", "Молот", "signals.hammer", "signal"),
    Pattern("harami", "Харами мягкое", "signals.harami", "flexible_harami"),
    Pattern("harami_strict", "Харами строгое", "signals.harami", "strict_harami"),
    Pattern("hikkake", "Хиккаке", "signals.hikkake", "signal"),
    Pattern("inside_up_down", "Внутренний бар", "signals.inside_up_down", "signal"),
    Pattern("marubozu", "Марубозу", "signals.marubozu", "marubozu"),
    Pattern("on_neck", "На шее", "signals.on_neck", "signal"),
    Pattern("piercing", "Просвет", "signals.piercing", "signal", "oc"),
    Pattern("quintuplets", "Пятерня", "signals.quintuplets", "signal", "oc"),
    Pattern("slingshot", "Рогатка", "signals.slingshot", "signal"),
    Pattern("spinning_top", "Волчок", "signals.spinning_top", "signal"),
    Pattern("star", "Звезда", "signals.star", "signal"),
    Pattern("stick_sandwich", "Бутерброд", "signals.stick_sandwich", "signal"),
    Pattern("tasuki", "Тасуки", "signals.tasuki", "tasuki", "oc"),
    Pattern(
        "three_candies",
        "Три свечи",
        "signals.the_three_candies_pattern",
        "the_three_candies_pattern",
        "oc",
    ),
    Pattern("three_methods", "Три метода", "signals.the_three_methods", "the_three_methods"),
    Pattern("the_h", "Буква H", "signals.theH", "signal"),
    Pattern("tower", "Башня", "signals.tower", "signal"),
    Pattern("tweezers", "Пинцет", "signals.tweezers", "signal"),
)


def build_matrix(candles: list[dict[str, Any]]) -> np.ndarray:
    """Свечи -> матрица [open, high, low, close, buy, sell, atr]."""
    matrix = np.zeros((len(candles), MATRIX_COLUMNS), dtype=float)
    for row, candle in enumerate(candles):
        matrix[row, OPEN] = to_float(candle["open"])
        matrix[row, HIGH] = to_float(candle["high"])
        matrix[row, LOW] = to_float(candle["low"])
        matrix[row, CLOSE] = to_float(candle["close"])
    matrix[:, ATR] = _atr_column(matrix)
    return matrix


def _atr_column(matrix: np.ndarray) -> list[float]:
    """ATR заполняется нулями там, где истории мало — так его ждут паттерны."""
    values = atr(
        list(matrix[:, HIGH]),
        list(matrix[:, LOW]),
        list(matrix[:, CLOSE]),
    )
    return [0.0 if value is None else value for value in values]


def run_pattern(pattern: Pattern, matrix: np.ndarray) -> np.ndarray:
    """Вызывает функцию паттерна и возвращает матрицу с отметками."""
    module = importlib.import_module(pattern.module)
    function = getattr(module, pattern.function)
    data = matrix.copy()

    if pattern.args == "self":
        return np.asarray(function(data))
    if pattern.args == "oc":
        return np.asarray(function(data, OPEN, CLOSE, BUY, SELL))
    if pattern.args == "atr":
        return np.asarray(function(data, OPEN, HIGH, LOW, CLOSE, ATR, BUY, SELL))
    return np.asarray(function(data, OPEN, HIGH, LOW, CLOSE, BUY, SELL))


def detect_signals(
    candles: list[dict[str, Any]],
    matrix: np.ndarray,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Прогоняет все паттерны и возвращает (сигналы, статистику по паттернам)."""
    signals: list[dict[str, Any]] = []
    summary: list[dict[str, Any]] = []

    for pattern in PATTERNS:
        try:
            data = run_pattern(pattern, matrix)
        except Exception as exc:  # noqa: BLE001 - один паттерн не должен ломать ответ
            logger.warning("паттерн %s не посчитался: %s", pattern.id, exc)
            summary.append({"id": pattern.id, "title": pattern.title, "count": 0, "error": str(exc)})
            continue

        count = 0
        for row in range(min(len(data), len(candles))):
            for column, direction in ((BUY, "buy"), (SELL, "sell")):
                if not data[row, column]:
                    continue
                candle = candles[row]
                signals.append(
                    {
                        "time": candle["time"],
                        "pattern": pattern.id,
                        "title": pattern.title,
                        "direction": direction,
                        # вход — по открытию бара, на котором сработал сигнал
                        "price": to_float(candle["open"]),
                    }
                )
                count += 1

        summary.append({"id": pattern.id, "title": pattern.title, "count": count})

    signals.sort(key=lambda item: (item["time"], item["pattern"]))
    return signals, summary


def build_indicators(candles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Индикаторы, выровненные по времени свечей (None-точки не отдаём)."""
    close = [to_float(candle["close"]) for candle in candles]
    high = [to_float(candle["high"]) for candle in candles]
    low = [to_float(candle["low"]) for candle in candles]

    series: dict[str, list[float | None]] = {
        "sma20": sma(close, 20),
        "ema50": ema(close, 50),
        "rsi14": rsi(close, 14),
        "atr14": atr(high, low, close, 14),
    }

    result: list[dict[str, Any]] = []
    for indicator_id, title, panel, period in INDICATORS:
        values = [
            {"time": candles[index]["time"], "value": round(value, 4)}
            for index, value in enumerate(series[indicator_id])
            if value is not None
        ]
        result.append(
            {
                "id": indicator_id,
                "title": title,
                "panel": panel,
                "period": period,
                "values": values,
            }
        )
    return result


def analyze(
    candles: list[dict[str, Any]],
    instrument_id: str,
    interval: str,
    days: int,
    source: str,
) -> dict[str, Any]:
    """Полный ответ аналитики по окну свечей."""
    matrix = build_matrix(candles)
    signals, patterns = detect_signals(candles, matrix)

    return {
        "instrument_id": instrument_id,
        "interval": interval,
        "days": days,
        "source": source,
        "candles": len(candles),
        "indicators": build_indicators(candles),
        "patterns": patterns,
        "signals": signals,
    }
