"""Хранение свечей в PostgreSQL.

Одна таблица `candles` с первичным ключом (instrument_id, interval, time).
Цены лежат как numeric(20,9) — точное представление Quotation {units, nano},
поэтому обратное преобразование не теряет наносекунды точности.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal
from typing import Any

import psycopg2

logger = logging.getLogger("investor.storage")

DATABASE_URL = os.getenv("DATABASE_URL", "")
NANO = Decimal(1_000_000_000)

Key = tuple[str, str, int]

SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS candles (
        instrument_id text          NOT NULL,
        interval      text          NOT NULL,
        time          timestamptz   NOT NULL,
        open          numeric(20,9) NOT NULL,
        high          numeric(20,9) NOT NULL,
        low           numeric(20,9) NOT NULL,
        close         numeric(20,9) NOT NULL,
        volume        bigint        NOT NULL,
        is_complete   boolean       NOT NULL DEFAULT true,
        PRIMARY KEY (instrument_id, interval, time)
    )
    """,
    "CREATE INDEX IF NOT EXISTS candles_lookup "
    "ON candles (instrument_id, interval, time DESC)",
)


def quotation_to_decimal(quotation: dict[str, int]) -> Decimal:
    return Decimal(int(quotation["units"])) + Decimal(int(quotation["nano"])) / NANO


def decimal_to_quotation(value: Decimal) -> dict[str, int]:
    units = int(value)
    nano = int((value - Decimal(units)) * NANO)
    return {"units": units, "nano": nano}


class CandleStorage:
    """Тонкий слой над таблицей. Соединение открывается на операцию:
    так нет протухших коннектов и не нужен пул при нагрузке в один процесс."""

    def __init__(self, dsn: str) -> None:
        if not dsn:
            raise RuntimeError("DATABASE_URL не задан")
        self.dsn = dsn

    @contextmanager
    def _connect(self) -> Iterator[psycopg2.extensions.connection]:
        conn = psycopg2.connect(self.dsn, connect_timeout=5)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def ensure_schema(self) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            for statement in SCHEMA_STATEMENTS:
                cur.execute(statement)
        logger.info("схема candles готова")

    def bounds(self, key: Key) -> tuple[datetime, datetime] | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT min(time), max(time) FROM candles "
                "WHERE instrument_id = %s AND interval = %s",
                (key[0], key[1]),
            )
            row = cur.fetchone()
        if not row or row[0] is None:
            return None
        return row[0], row[1]

    def upsert(self, key: Key, candles: list[dict[str, Any]]) -> int:
        if not candles:
            return 0

        rows = [
            (
                key[0],
                key[1],
                candle["time"],
                quotation_to_decimal(candle["open"]),
                quotation_to_decimal(candle["high"]),
                quotation_to_decimal(candle["low"]),
                quotation_to_decimal(candle["close"]),
                int(candle["volume"]),
                bool(candle["isComplete"]),
            )
            for candle in candles
        ]

        with self._connect() as conn, conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO candles
                    (instrument_id, interval, time, open, high, low, close, volume, is_complete)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (instrument_id, interval, time) DO UPDATE SET
                    open = EXCLUDED.open,
                    high = EXCLUDED.high,
                    low = EXCLUDED.low,
                    close = EXCLUDED.close,
                    volume = EXCLUDED.volume,
                    is_complete = EXCLUDED.is_complete
                """,
                rows,
            )
        return len(rows)

    def load(self, key: Key, start: datetime, end: datetime) -> list[dict[str, Any]]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT time, open, high, low, close, volume, is_complete
                FROM candles
                WHERE instrument_id = %s AND interval = %s AND time BETWEEN %s AND %s
                ORDER BY time
                """,
                (key[0], key[1], start, end),
            )
            rows = cur.fetchall()

        return [
            {
                "open": decimal_to_quotation(row[1]),
                "high": decimal_to_quotation(row[2]),
                "low": decimal_to_quotation(row[3]),
                "close": decimal_to_quotation(row[4]),
                "volume": int(row[5]),
                "time": row[0],
                "isComplete": bool(row[6]),
            }
            for row in rows
        ]

    def stats(self, key: Key) -> dict[str, Any]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT count(*), min(time), max(time) FROM candles "
                "WHERE instrument_id = %s AND interval = %s",
                (key[0], key[1]),
            )
            row = cur.fetchone()
        return {
            "rows": int(row[0]) if row else 0,
            "min_time": row[1].isoformat() if row and row[1] else None,
            "max_time": row[2].isoformat() if row and row[2] else None,
        }
