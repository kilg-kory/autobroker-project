"""Проверка боевого кода проекта: импорты, вызовы, API. Без БД, MT5 и сети.

Секции:
  signals    - каждый модуль signals/ вызывается на синтетических OHLC
  indicators - ma, smoothed_ma, rsi, atr
  services   - импорт market.candles, service.analysis, service.performance
  api        - реальные запросы к FastAPI через тестовый клиент

Запуск из корня проекта:

    .venv\\Scripts\\python.exe check_project.py

Зачем: 14 модулей signals/ падали с NameError только в момент вызова, а не при
импорте, поэтому проверка "import signals.x" их не ловила.

Учебные материалы (ноутбуки, главы из книг, старый Flask/SQLAlchemy) лежат в
learning/ — их этот скрипт не проверяет.
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
import sys
import traceback
from pathlib import Path

import numpy as np

# Модули разнесены по project/*, поэтому добавляем их в sys.path,
# чтобы скрипт запускался из корня: python check_project.py
ROOT = Path(__file__).resolve().parent
INVESTOR = ROOT / "project" / "investor"
BACKEND = ROOT / "project" / "backend"
for _path in (BACKEND, INVESTOR):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

# Имена параметров -> индексы колонок в массиве [open, high, low, close, buy, sell]
COLUMNS = {
    "open_column": 0,
    "high_column": 1,
    "low_column": 2,
    "close_column": 3,
    "buy_column": 4,
    "sell_column": 5,
    "atr_column": 6,
}

# Служебные параметры: функции вида f(data, i, ...) — это построчные хелперы
PER_BAR_PARAMS = {"i", "index"}

failures: list[tuple[str, str]] = []


def ok(label: str, extra: str = "") -> None:
    print(f"[OK]   {label}{extra}")


def fail(label: str, exc: BaseException | str) -> None:
    message = exc if isinstance(exc, str) else f"{type(exc).__name__}: {exc}"
    failures.append((label, message))
    print(f"[FAIL] {label}: {message}")
    if isinstance(exc, BaseException):
        traceback.print_exc(limit=2)


def make_ohlc(n: int = 600, seed: int = 0) -> np.ndarray:
    """Случайное блуждание, похожее на M15 EURUSD по масштабу свечей."""
    rng = np.random.default_rng(seed)
    close = 1.10 + np.cumsum(rng.normal(0, 0.0005, n))
    open_ = close + rng.normal(0, 0.0002, n)
    high = np.maximum(open_, close) + np.abs(rng.normal(0, 0.0002, n))
    low = np.minimum(open_, close) - np.abs(rng.normal(0, 0.0002, n))
    data = np.column_stack([open_, high, low, close]).astype(float)
    # резерв под buy/sell/atr: atr_column должен содержать числа, а не нули
    return np.hstack([data, np.full((n, 4), 0.0005, dtype=float)])


def call_signal(func, data: np.ndarray) -> np.ndarray:
    """Подставляет колонки по именам параметров — сигнатуры у модулей разные."""
    kwargs = {}
    for name, param in inspect.signature(func).parameters.items():
        if name == "data":
            continue
        if name in COLUMNS:
            kwargs[name] = COLUMNS[name]
        elif param.default is inspect.Parameter.empty:
            kwargs[name] = 20  # запасное значение для lookback и подобных
    return func(data, **kwargs)


def candidates(module) -> list:
    """signal(), иначе функция с именем модуля, иначе все публичные функции модуля."""
    funcs = [
        obj
        for obj in vars(module).values()
        if inspect.isfunction(obj) and obj.__module__ == module.__name__
    ]
    if not funcs:
        return []
    for func in funcs:
        if func.__name__ == "signal":
            return [func]
    module_name = module.__name__.rsplit(".", 1)[-1]
    named = [func for func in funcs if func.__name__ == module_name]
    return named or funcs


def check_signals() -> None:
    import signals  # namespace-пакет, __init__.py нет

    names = sorted(m.name for m in pkgutil.iter_modules(signals.__path__))
    for name in names:
        module = importlib.import_module(f"signals.{name}")
        funcs = [
            f for f in candidates(module)
            if not (PER_BAR_PARAMS & set(inspect.signature(f).parameters))
        ]
        if not funcs:
            fail(name, "нет вызываемых функций")
            continue
        for func in funcs:
            label = name if func.__name__ in ("signal", name) else f"{name}.{func.__name__}"
            try:
                result = call_signal(func, make_ohlc())
                if result.ndim != 2 or result.shape[1] < 6:
                    raise AssertionError(f"bad output shape {result.shape}")
                ok(label)
            except Exception as exc:  # noqa: BLE001
                fail(label, exc)
    print(f"  -> {len(names)} modules in signals/ checked")


def check_indicators() -> None:
    from indicators.atr import atr
    from indicators.ma import ma
    from indicators.rsi import rsi
    from indicators.smoothed_ma import smoothed_ma

    cases = {
        "ma": lambda d: ma(d, 20, 3, 4),
        "smoothed_ma": lambda d: smoothed_ma(d, 2, 10, 3, 4),
        "rsi": lambda d: rsi(d, 14, 3, 4),
        "atr": lambda d: atr(d, 14, 1, 2, 3, 4),
    }
    for name, case in cases.items():
        try:
            result = case(make_ohlc())
            ok(f"indicators.{name}", f" -> shape {result.shape}")
        except Exception as exc:  # noqa: BLE001
            fail(f"indicators.{name}", exc)


def check_services() -> None:
    """Импорт боевых модулей: ловит битые импорты, но не требует поднятой БД."""
    for name in (
        "market.candles",
        "service.analysis",
        "service.performance",
        "fastapi_server.app",
    ):
        try:
            importlib.import_module(name)
            ok(f"import {name}")
        except Exception as exc:  # noqa: BLE001
            fail(f"import {name}", exc)


def check_fastapi() -> None:
    from fastapi.testclient import TestClient

    from fastapi_server.app import app

    client = TestClient(app)

    def step(label, response, expected):
        if response.status_code != expected:
            raise AssertionError(f"{label}: {response.status_code} != {expected} {response.text}")
        return response

    try:
        step("GET /", client.get("/"), 200)
        created = step("POST /tasks/create", client.post(
            "/tasks/create", json={"title": "t1"}), 200).json()
        task_id = created["task"]["id"]
        step("GET task", client.get(f"/tasks/task/{task_id}"), 200)
        step("GET list", client.get("/tasks/list?skip=0&limit=10"), 200)
        step("PUT task", client.put(
            f"/tasks/task/{task_id}", json={"title": "t2"}), 200)
        step("PUT missing", client.put(
            "/tasks/task/999", json={"title": "x"}), 404)
        step("DELETE task", client.delete(f"/tasks/task/{task_id}"), 200)
        step("DELETE again", client.delete(f"/tasks/task/{task_id}"), 404)
        ok("fastapi endpoints")
    except Exception as exc:  # noqa: BLE001
        fail("fastapi endpoints", exc)


def main() -> None:
    for title, check in (
        ("signals", check_signals),
        ("indicators", check_indicators),
        ("services (import only)", check_services),
        ("api (fastapi)", check_fastapi),
    ):
        print(f"\n== {title} ==")
        try:
            check()
        except Exception as exc:  # noqa: BLE001
            fail(title, exc)

    if failures:
        print(f"\nFAILED: {len(failures)}")
        for name, message in failures:
            print(f"  - {name}: {message}")
        raise SystemExit(1)
    print("\nALL CHECKS PASSED")


if __name__ == "__main__":
    main()
