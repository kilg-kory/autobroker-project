"""Утилиты для матричных расчётов и загрузки котировок.

Модуль пришёл из песочницы, где данные брались из MetaTrader5. Сервису
investor MT5 не нужен: для расчёта сигналов достаточно `add_column`,
`rounding`, `delete_column`, `del_row` и `add_row` — они работают на numpy.
Поэтому тяжёлые зависимости (MetaTrader5, pandas, pytz, matplotlib)
импортируются лениво, внутри функций, которым они действительно нужны.
Из-за этого `signals/*` и `indicators/*` импортируются в контейнере, где
ни MT5, ни matplotlib нет.
"""

from __future__ import annotations

import datetime

import numpy as np


def add_column(data, times):
    for _ in range(1, times + 1):
        new = np.zeros((len(data), 1), dtype=float)
        data = np.append(data, new, axis=1)
    return data


def delete_column(data, index, times):
    for _ in range(1, times + 1):
        data = np.delete(data, index, axis=1)
    return data


def add_row(data, times):
    for _ in range(1, times + 1):
        columns = np.shape(data)[1]
        new = np.zeros((1, columns), dtype=float)
        data = np.append(data, new, axis=0)
    return data


def del_row(data, number):
    return data[number:,]


def rounding(data, how_far):
    return data.round(decimals=how_far)


def _mt5():
    """Импорт MT5 по требованию: локально он есть, в контейнере — нет."""
    import MetaTrader5 as mt5  # noqa: PLC0415

    return mt5


def get_quotes(time_frame, year=2025, month=1, day=1, asset="EURUSD"):
    import pytz  # noqa: PLC0415
    import pandas as pd  # noqa: PLC0415

    mt5 = _mt5()
    if not mt5.initialize():
        raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")

    timezone = pytz.timezone("Europe/Moscow")
    time_from = datetime.datetime(year, month, day, tzinfo=timezone)
    time_to = datetime.datetime.now(timezone) + datetime.timedelta(days=1)
    rates = mt5.copy_rates_range(asset, time_frame, time_from, time_to)
    return pd.DataFrame(rates)


def mass_import(asset, time_frame):
    mt5 = _mt5()
    frames = {"H1": mt5.TIMEFRAME_H1, "D1": mt5.TIMEFRAME_D1}
    assets = [
        "EURUSD",
        "USDCHF",
        "GBPUSD",
        "USDCAD",
        "BTCUSD",
        "ETHUSD",
        "XAUUSD",
        "SP500m",
        "UK100",
    ]
    year = 2025 if time_frame == "H1" else 2026
    data = get_quotes(frames[time_frame], year, 1, 1, asset=assets[asset])
    return data.iloc[:, 1:5].values.round(decimals=5)
