from datetime import datetime
from typing import Literal

from pydantic import BaseModel

# sqlalchemy models


# pydantic schemas

class Task(BaseModel):
    title: str
    description: str | None = None  # Необязательное поле, по умолчанию None
    is_completed: bool = False      # По умолчанию задача не выполнена


class Quotation(BaseModel):
    """Деньги в T-Invest API: units + nano (10^-9)."""

    units: int
    nano: int


class HistoricCandle(BaseModel):
    """Свеча в форме t_tech.invest. camelCase — чтобы совпадать с типами фронтенда."""

    open: Quotation
    high: Quotation
    low: Quotation
    close: Quotation
    volume: int
    time: datetime
    isComplete: bool


class IndicatorPoint(BaseModel):
    """Точка индикатора: время свечи и значение."""

    time: datetime
    value: float


class IndicatorSeries(BaseModel):
    """Ряд индикатора. `panel` говорит фронтенду, на какую панель его рисовать."""

    id: str
    title: str
    panel: Literal["price", "rsi", "atr"]
    period: int
    values: list[IndicatorPoint]


class PatternInfo(BaseModel):
    """Паттерн и сколько раз он сработал в окне."""

    id: str
    title: str
    count: int
    error: str | None = None


class SignalPoint(BaseModel):
    """Отметка паттерна: бар входа, направление и цена открытия."""

    time: datetime
    pattern: str
    title: str
    direction: Literal["buy", "sell"]
    price: float


class AnalysisResponse(BaseModel):
    """Ответ investor /analysis как есть."""

    instrument_id: str
    interval: str
    days: int
    source: str
    candles: int
    indicators: list[IndicatorSeries]
    patterns: list[PatternInfo]
    signals: list[SignalPoint]


class PerformanceRow(BaseModel):
    """Бэктест одного паттерна по правилам `util/performance.py`.

    `None` в коэффициентах означает «не определено»: делитель нулевой
    (например, у набора без убыточных сделок profit factor посчитать нельзя).
    """

    id: str
    title: str
    signals: int
    #: сигналы, у которых в окне не нашлось закрывающего — в сделки не вошли
    open_trades: int
    trades: int
    hit_ratio: float | None
    profit_factor: float | None
    risk_reward: float | None
    net_result: float
    avg_result: float | None
    best: float | None
    worst: float | None


class PerformanceTotal(BaseModel):
    """Итог по выбранным паттернам: сделки всех паттернов в одном наборе."""

    patterns: int
    signals: int
    trades: int
    hit_ratio: float | None
    profit_factor: float | None
    risk_reward: float | None
    net_result: float
    avg_result: float | None
    best: float | None
    worst: float | None


class AvailablePattern(BaseModel):
    """Паттерн, который срабатывал в окне — из него строится список галочек."""

    id: str
    title: str
    signals: int


class PerformanceResponse(BaseModel):
    """Ответ investor /performance как есть."""

    instrument_id: str
    interval: str
    days: int
    source: str
    candles: int
    patterns: list[PerformanceRow]
    total: PerformanceTotal
    available: list[AvailablePattern]
