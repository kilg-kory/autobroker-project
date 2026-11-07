# project

Три части: `investor` (данные), `backend` (REST для UI), `frontend` (React).

## Как они связаны

```
frontend ──GET /api/candles─────▶ backend ──HTTP──▶ investor ──▶ T-Invest API
         ──GET /api/analysis────▶                    │
         ──GET /api/performance─▶              PostgreSQL
```

- **investor** — самостоятельный сервис. Свечи лежат в PostgreSQL, у T-Invest
  докачиваются только недостающие интервалы. Фоновое обновление идёт по
  расписанию и не зависит от того, подключён ли кто-то. Здесь же считается
  аналитика: индикаторы (SMA/EMA/RSI/ATR), сигналы 27 паттернов из `signals/`
  и их бэктест (hit ratio, profit factor, risk/reward).
- **backend** — REST для фронтенда, кэширует ответы investor на 5 секунд.
  Знает про investor только `INVESTOR_API_URL`.
- **frontend** — React + MUI + RTK Query, проксирует `/api` на backend.

Никто не импортирует код соседа — только сетевые вызовы и SQL к своей базе.
Поэтому сервисы разъезжаются по контейнерам и машинам без правок кода.

## Что где лежит

В `project/` — только боевой код: сервисы, их Dockerfile'ы, `compose.yaml` и
документация. Дальше по корню:

| Куда | Что |
|---|---|
| `../data/` | PostgreSQL (`data/postgres`, bind-mount) и бэкап `data/dump.sql` |
| `../learning/investor_book/` | главы `ch*.py`, `charts/`, `tryTAPI.ipynb`, пример `performance.py` |
| `../learning/backend_legacy/` | `flask_articles.py`, `db/`, SQL-процедура, старый compose |
| `../learning/frontend_legacy/` | неиспользуемые картинки из шаблона MUI |
| `../learning/legacy_docs/` | диаграмма разнесения сервисов и скрипт её отрисовки |
| `../learning/` (остальное) | ноутбуки и книги по pandas, numpy, ML |
| `../check_project.py` | проверка боевого кода: сигналы, индикаторы, импорты, API |

Данные лежат уровнем выше `project/`, потому что это состояние, а не код:
`git` и Docker-образы их не видят, а `compose.yaml` подключает каталог
относительным путём. Скриншоты интерфейса живут в `frontend/docs/` — на них
ссылается README фронтенда.

Проверка боевого кода — `check_project.py` из корня: сигналы, индикаторы,
импорты сервисов и API FastAPI.

## Запуск локально

```bash
# 0) окружение для сервисов — один раз, из project/ (Python 3.12+)
python -m venv .venv
.venv\Scripts\activate
pip install -r investor\requirements.txt -r backend\requirements.txt

# 1) Postgres (или docker compose up postgres из project/)
#    DATABASE_URL=postgresql://investor:investor@127.0.0.1:5433/investor

# 2) investor (порт 8100) — из project/investor
..\.venv\Scripts\python.exe -m uvicorn service.app:app --port 8100

# 3) backend (порт 8000) — из project/backend
..\.venv\Scripts\python.exe -m uvicorn fastapi_server.app:app --port 8000

# 4) frontend (порт 5173) — из project/frontend
pnpm dev
```

Для реальных данных вместо мока нужен ещё SDK T-Invest — он ставится не из PyPI,
команда есть в [investor/README.md](investor/README.md#docker). Без него investor
работает: если `TOKEN` не задан, отдаёт детерминированный мок того же формата.

## Docker

```bash
cd project
docker compose up --build
```

Поднимаются четыре сервиса:

| Сервис | Порт | Образ |
|---|---|---|
| `postgres` | 5433 → 5432 | `postgres:16-alpine`, данные в `../data/postgres` |
| `investor` | 8100 | сборка из `investor/Dockerfile` |
| `backend` | 8000 | сборка из `backend/Dockerfile` |
| `frontend` | 8080 → 80 | сборка из `frontend/Dockerfile`, раздача через nginx |

UI: <http://localhost:8080> — nginx отдаёт статику и проксирует `/api/` на backend.

Связи внутри сети compose: nginx → `http://backend:8000`,
backend → `http://investor:8100`, investor → `postgres:5432`.
Наружу проброшены только порты приложения и базы.

Порядок запуска обеспечивают healthcheck'и: backend ждёт healthy investor,
investor — healthy postgres.

### Данные Postgres

Каталог `../data/postgres` (в корне репозитория, рядом с `project/`) смонтирован
в контейнер напрямую, поэтому база переживает `docker compose restart`, `down`
и пересборку образов. Каталог добавлен в `.gitignore`.

Данные лежат вне `project/` намеренно: код сервисов остаётся без состояния, а
каталог с базой не попадает ни в образы (там `.dockerignore`), ни в архив с
кодом. `compose.yaml` ссылается на него относительным путём `../data/postgres`.

Побочный плюс по сравнению с именованным томом: `docker compose down -v` больше
не стирает базу — `-v` удаляет только именованные тома, локальный каталог остаётся.

Бэкап и восстановление (из `project/`):

```bash
# дамп на хост
docker compose exec -T postgres pg_dump -U investor -d investor --no-owner -f /tmp/dump.sql
docker cp project-postgres-1:/tmp/dump.sql ../data/dump.sql

# восстановление в чистую базу
docker compose down
rm -rf ../data/postgres
docker compose up -d postgres
docker cp ../data/dump.sql project-postgres-1:/tmp/dump.sql
docker compose exec -T postgres psql -U investor -d investor -f /tmp/dump.sql
```

Отдельный «сид» не нужен: если база пустая, `investor` наполнит её сам —
при старте прогревает `WARMUP_*`-ключи и докачивает недостающие интервалы у T-Invest.

Чтобы разнести по разным машинам, меняется только `INVESTOR_API_URL`
у backend, например `http://10.0.0.5:8100`.

### Про SDK T-Invest

`t-tech-investments` нет в PyPI — он лежит в GitLab Package Registry TBank:

```
https://opensource.tbank.ru/api/v4/projects/238/packages/pypi/simple
```

Dockerfile ставит его оттуда как **дополнительный** индекс (зависимости SDK идут
из PyPI), а `--trusted-host` обходит корпоративный CA. Обе настройки — build-args
`TINVEST_INDEX_URL` и `TINVEST_TRUSTED_HOST`. Документация SDK:
<https://developer.tbank.ru/invest/sdk/python_sdk/faq_python>.

## Контракт

Обе границы — REST + JSON. Форма свечи одна и та же (`HistoricCandle` из T-Invest):
цены как `Quotation { units, nano }`, время ISO 8601, флаг `isComplete`.

Заголовки для отладки:

| Заголовок | Кто отдаёт | Смысл |
|---|---|---|
| `X-Data-Source` | investor → backend | `tinvest`, `postgres` или `mock` |
| `X-Candles-Count` | investor | сколько свечей в ответе |
| `X-Signals-Count` | investor → backend | сколько отметок паттернов в `/analysis` |
| `X-Cache` | backend | `HIT` / `MISS` |
| `X-Cache-TTL` | backend | TTL кэша в секундах |

### Аналитика

`GET /api/analysis` отдаёт индикаторы и сигналы по тому же окну свечей:

```json
{
  "candles": 575,
  "indicators": [
    {"id": "rsi14", "title": "RSI 14", "panel": "rsi", "period": 14,
     "values": [{"time": "2026-11-06T14:00:00+00:00", "value": 55.62}]}
  ],
  "patterns": [{"id": "base_signal", "title": "Базовая альфа", "count": 102}],
  "signals": [
    {"time": "2026-11-07T02:00:00+00:00", "pattern": "base_signal",
     "title": "Базовая альфа", "direction": "buy", "price": 294.5}
  ]
}
```

Индикаторы: `sma20` и `ema50` (на цене), `rsi14` и `atr14` (на отдельных панелях).
Сигналы — разметка 27 паттернов из `investor/signals/`; `time` — бар входа
(сигнал ставится на следующий бар после подтверждения), `price` — его открытие.
Подробности: [investor/README.md](investor/README.md#аналитика-analysis).

### Производительность

`GET /api/performance` — бэктест сигналов по правилам из
`investor/service/performance.py`: вход по открытию бара сигнала, выход по
открытию следующего сигнала того же паттерна, без комиссий и стопов.

```json
{
  "patterns": [
    {"id": "tasuki", "title": "Тасуки", "signals": 28, "open_trades": 1,
     "trades": 27, "hit_ratio": 51.85, "profit_factor": 1.74,
     "risk_reward": 1.61, "net_result": 14.57}
  ],
  "total": {"patterns": 21, "signals": 298, "trades": 277},
  "available": [{"id": "tasuki", "title": "Тасуки", "signals": 28}]
}
```

Метрики на паттерн: `trades`, `hit_ratio` (%), `profit_factor`,
`risk_reward`, `net_result` в рублях на акцию, плюс `best` / `worst`.
`null` в коэффициентах — «не определено» (делитель нулевой).

Параметр `patterns=id1,id2` считает только выбранные паттерны — на нём
построен пересчёт таблицы с включёнными и выключенными сигналами;
`patterns=` (пустая строка) означает «не выбран ни один», а отсутствие
параметра — «считать все».
Подробности: [investor/README.md](investor/README.md#производительность-performance).

## Подробности

- [investor/README.md](investor/README.md) — хранение в Postgres, план докачки, фоновое обновление
- [backend/README.md](backend/README.md) — эндпоинты, кэш, переменные окружения
- [frontend/README.md](frontend/README.md) — UI, график, сборка
