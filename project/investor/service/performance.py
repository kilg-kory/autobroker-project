"""Производительность паттернов — бэктест по правилам из книги.

Правила взяты из учебного примера `learning/investor_book/util/performance.py`
(он был `util/performance.py`, пока не переехал в архив) без изменений:

- вход — по цене открытия бара, на котором сработал сигнал;
- выход — по открытию следующего сигнала этого же паттерна в любую сторону;
- результат лонга  = open(выход) - open(вход);
- результат шорта = open(вход) - open(выход);
- комиссии и проскальзывание не учитываются, стопов нет;
- сигнал без закрывающего сигнала в окне в статистику не попадает
  (в примере такой «хвост» тоже молча терялся).

Считается поверх тех же сигналов, что отдаёт `/analysis`, поэтому цифры в
таблице и отметки на графике всегда совпадают.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any

from service import analysis

logger = logging.getLogger("investor.performance")


def _metrics(results: list[float]) -> dict[str, Any]:
    """Метрики набора сделок — те же четыре из примера плюс суммы.

    None в `profit_factor` / `risk_reward` означает «не определено»:
    в примере деление на пустой набор давало inf или nan.
    """
    if not results:
        return {
            "trades": 0,
            "hit_ratio": None,
            "profit_factor": None,
            "risk_reward": None,
            "net_result": 0.0,
            "avg_result": None,
            "best": None,
            "worst": None,
        }

    profits = [value for value in results if value > 0]
    losses = [value for value in results if value < 0]

    def _ratio(numerator: float, denominator: float) -> float | None:
        return None if denominator == 0 else round(numerator / denominator, 3)

    net = sum(results)
    return {
        "trades": len(results),
        "hit_ratio": round(len(profits) / len(results) * 100, 2),
        "profit_factor": _ratio(sum(profits), abs(sum(losses))),
        "risk_reward": _ratio(
            sum(profits) / len(profits) if profits else 0.0,
            abs(sum(losses) / len(losses)) if losses else 0.0,
        ),
        "net_result": round(net, 4),
        "avg_result": round(net / len(results), 4),
        "best": round(max(results), 4),
        "worst": round(min(results), 4),
    }


def _trade_results(
    signals: list[dict[str, Any]],
    open_by_time: dict[str, float],
) -> list[float]:
    """Результаты сделок одного паттерна по правилам `performance.py`.

    Сигналы уже отсортированы по времени, поэтому выход — просто следующий
    сигнал в списке, в какую бы сторону он ни был.
    """
    results: list[float] = []

    for index, signal in enumerate(signals[:-1]):
        entry_price = open_by_time.get(signal["time"])
        exit_price = open_by_time.get(signals[index + 1]["time"])
        if entry_price is None or exit_price is None:
            continue

        if signal["direction"] == "buy":
            results.append(exit_price - entry_price)
        else:
            results.append(entry_price - exit_price)

    return results


def evaluate(
    candles: list[dict[str, Any]],
    pattern_ids: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Считает производительность выбранных паттернов.

    `pattern_ids=None` — все паттерны окна. Паттерны, которых нет в окне,
    в ответ не попадают: врать нулями про «включённый» паттерн хуже, чем
    не показать его вовсе.
    """
    matrix = analysis.build_matrix(candles)
    signals, patterns = analysis.detect_signals(candles, matrix)

    open_by_time = {
        candle["time"]: analysis.to_float(candle["open"]) for candle in candles
    }

    by_pattern: dict[str, list[dict[str, Any]]] = {}
    for signal in signals:
        by_pattern.setdefault(signal["pattern"], []).append(signal)

    selected = None if pattern_ids is None else {item for item in pattern_ids}
    titles = {pattern["id"]: pattern["title"] for pattern in patterns}

    rows: list[dict[str, Any]] = []
    summary_signals = 0
    summary_results: list[float] = []

    for pattern_id, pattern_signals in by_pattern.items():
        if selected is not None and pattern_id not in selected:
            continue

        results = _trade_results(pattern_signals, open_by_time)
        summary_signals += len(pattern_signals)
        summary_results.extend(results)
        rows.append(
            {
                "id": pattern_id,
                "title": titles.get(pattern_id, pattern_id),
                "signals": len(pattern_signals),
                "open_trades": len(pattern_signals) - len(results) if pattern_signals else 0,
                **_metrics(results),
            }
        )

    rows.sort(key=lambda row: (row["net_result"] is None, -(row["net_result"] or 0.0)))

    total = {
        "patterns": len(rows),
        "signals": summary_signals,
        **_metrics(summary_results),
    }

    return {
        "patterns": rows,
        "total": total,
        "available": [
            {
                "id": pattern["id"],
                "title": pattern["title"],
                "signals": pattern["count"],
            }
            for pattern in patterns
            if pattern["count"] > 0
        ],
    }
