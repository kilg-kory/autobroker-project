# Backend

FastAPI-сервис: отдаёт свечи и аналитику, полученные от сервиса `investor`
по HTTP, и кэширует их на 5 секунд.

## Запуск

Окружение `project/.venv` создаётся один раз — см. «Запуск локально» в
[../README.md](../README.md).

Сначала поднимается investor (из `project/investor`):

```bash
..\.venv\Scripts\python.exe -m uvicorn service.app:app --port 8100
```

Затем backend (из `project/backend`):

```bash
..\.venv\Scripts\python.exe -m uvicorn fastapi_server.app:app --port 8000
```

- Swagger: <http://127.0.0.1:8000/docs>
- Фронтенд проксирует `/api` → `127.0.0.1:8000`.

## Переменные окружения

| Переменная | По умолчанию | Зачем |
|---|---|---|
| `INVESTOR_API_URL` | `http://127.0.0.1:8100` | адрес сервиса investor |
| `INVESTOR_TIMEOUT_SECONDS` | `15` | таймаут запроса к investor |
| `CACHE_TTL_SECONDS` | `5` | TTL собственного кэша |
| `INVESTOR_TRUST_ENV` | `0` | учитывать прокси из окружения |

`INVESTOR_TRUST_ENV=0` по умолчанию не случайно: httpx подхватывает системный
прокси (в Windows — из реестра WinINET), и тогда запросы к внутреннему адресу
уходят в прокси и падают с 503. Включать стоит только если investor доступен
исключительно через корпоративный прокси.

## Эндпоинты

| Метод | Путь | Описание |
|---|---|---|
| GET | `/candles` | свечи из investor, кэш 5 с |
| GET | `/analysis` | индикаторы и сигналы из investor, кэш 5 с |
| GET | `/performance` | бэктест сигналов из investor, кэш 5 с |
| GET | `/candles/cache/stats` | ttl, размер кэша, hits, misses |
| GET | `/analysis/cache/stats` | то же для кэша аналитики |
| GET | `/performance/cache/stats` | то же для кэша бэктеста |
| GET | `/tasks` и далее | учебный in-memory CRUD |

`GET /candles?instrument_id=BBG004730N88&interval=CANDLE_INTERVAL_HOUR&days=30`

Параметры:

- `instrument_id` — тикер в нотации T-Invest (по умолчанию Сбербанк);
- `interval` — `CANDLE_INTERVAL_MIN_15` | `CANDLE_INTERVAL_HOUR` | `CANDLE_INTERVAL_DAY`;
- `days` — глубина истории, 1..365.

Заголовки ответа:

| Заголовок | Значение |
|---|---|
| `X-Cache` | `MISS` — сходили в investor; `HIT` — отдали из кэша |
| `X-Cache-TTL` | TTL в секундах (сейчас 5) |
| `X-Data-Source` | проброшен от investor: `tinvest`, `postgres` или `mock` |
| `X-Signals-Count` | только `/analysis`: сколько отметок паттернов в ответе |

### `/analysis`

```json
{
  "instrument_id": "BBG004730N88",
  "interval": "CANDLE_INTERVAL_HOUR",
  "days": 30,
  "source": "postgres",
  "candles": 575,
  "indicators": [
    {"id": "sma20", "title": "SMA 20", "panel": "price", "period": 20,
     "values": [{"time": "2026-11-06T14:00:00+00:00", "value": 293.41}]}
  ],
  "patterns": [{"id": "base_signal", "title": "Базовая альфа", "count": 102}],
  "signals": [
    {"time": "2026-11-07T02:00:00+00:00", "pattern": "base_signal",
     "title": "Базовая альфа", "direction": "buy", "price": 294.5}
  ]
}
```

Backend ничего не пересчитывает: `signals` и `indicators` приходят из investor
как есть. Схемы лежат в `models.py` (`AnalysisResponse` и вложенные), поэтому
контракт зафиксирован и виден в Swagger.

`time` сигнала — бар, на котором сработал паттерн (вход по его открытию),
`price` — цена открытия этого бара.

### `/performance`

`GET /performance?instrument_id=BBG004730N88&interval=CANDLE_INTERVAL_HOUR&days=30&patterns=tasuki,three_candies`

Бэктест сигналов по правилам из `project/investor/service/performance.py`:
hit ratio, profit factor, risk/reward, число сделок. `patterns` — id через
запятую, без параметра считаются все паттерны окна; так клиент пересчитывает
таблицу, включая и выключая сигналы. Пустая строка (`patterns=`) — «не выбран
ни один паттерн» и передаётся в investor как есть, чтобы не путать с
отсутствием параметра.

```json
{
  "patterns": [
    {"id": "tasuki", "title": "Тасуки", "signals": 28, "open_trades": 1,
     "trades": 27, "hit_ratio": 51.85, "profit_factor": 1.74,
     "risk_reward": 1.61, "net_result": 14.57, "avg_result": 0.54,
     "best": 3.21, "worst": -1.9}
  ],
  "total": {"patterns": 21, "signals": 298, "trades": 277, "hit_ratio": 49.46},
  "available": [{"id": "tasuki", "title": "Тасуки", "signals": 28}]
}
```

`total` — сделки всех выбранных паттернов в одном наборе (сумма сигналов,
а не совместная торговля). `available` всегда содержит все сработавшие
паттерны: из него фронтенд строит список галочек.

Ключ кэша включает список паттернов, поэтому пересчёт с другим набором
сигналов не отдаёт чужой ответ. Заголовки: `X-Cache`, `X-Cache-TTL`,
`X-Data-Source`, `X-Patterns-Count`, `X-Trades-Count`.

## Как устроено

```
fastapi_server/
  app.py                 FastAPI + подключение роутеров
  config.py              настройки из окружения
  models.py              pydantic-схемы: Task, Quotation, HistoricCandle,
                         AnalysisResponse, PerformanceResponse
  cache.py               TTLCache: get/set/stats, без зависимостей
  investor_client.py     httpx-клиент сервиса investor (/candles, /analysis, /performance)
  routers/candles.py     GET /candles + кэширование
  routers/analysis.py    GET /analysis + кэширование
  routers/performance.py GET /performance + кэширование
  routers/tasks.py       учебный CRUD в памяти
```

Backend **не импортирует** investor: знает только URL и JSON-контракт
(`HistoricCandle`). Поэтому сервисы можно разнести по контейнерам и машинам,
поменяв одну переменную окружения.

Если investor недоступен, а кэш пуст — клиент получает `503` с понятным `detail`,
а не `500`. Когда investor поднимается, цепочка восстанавливается сама:
backend не кэширует ошибку.

## Кэш

`cache.py` — минимальная реализация: словарь с `expires_at` и счётчиками попаданий.
TTL задан константой `CACHE_TTL_SECONDS` (по умолчанию 5 с).

Дальше сюда можно поставить `cachetools.TTLCache` (уже установлен) или Redis —
интерфейс `get` / `set` / `stats` менять не придётся.

Ограничение: кэш живёт в памяти процесса, поэтому при `--workers N` у каждого
воркера будет свой кэш.

## Docker

Собирается из `Dockerfile` в этой папке; вместе с investor поднимается
через `project/compose.yaml`:

```bash
cd project
docker compose up --build
```

Внутри compose backend получает `INVESTOR_API_URL=http://investor:8100`,
то есть обращается к investor по имени сервиса, а не по localhost.
