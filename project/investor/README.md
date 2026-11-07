# Investor

Сервис данных: хранит свечи в PostgreSQL, докачивает у T-Invest только
недостающие интервалы и работает сам по себе — фоновое обновление не зависит
от подключённых клиентов.

## Запуск

Из `project/investor` (нужна переменная `DATABASE_URL`):

```bash
..\.venv\Scripts\python.exe -m uvicorn service.app:app --port 8100
```

Окружение `project/.venv` создаётся один раз — см. «Запуск локально» в
[../README.md](../README.md). Реальные данные требуют SDK T-Invest (команда ниже,
в разделе «Docker»); без него сервис отдаёт мок, если `TOKEN` не задан.

Обычно поднимается через `project/compose.yaml` — там Postgres уже настроен.

- Swagger: <http://127.0.0.1:8100/docs>
- `GET /candles` — свечи за окно
- `GET /health` — состояние и содержимое базы

## Как устроено

```
market/candles.py        источник: T-Invest API (таймаут на вызов — TINVEST_TIMEOUT_SECONDS), мок только без токена
service/storage.py       PostgreSQL: таблица candles, upsert, выборка по окну
service/store.py         план докачки + фоновый цикл обновления
service/analysis.py      индикаторы и разметка сигналов по свечам
service/performance.py   бэктест сигналов: hit ratio, profit factor, risk/reward
service/app.py           FastAPI: /candles, /analysis, /performance, /health
signals/, indicators/    паттерны и индикаторы из книги (в бою — через analysis.py)
util/data_utils.py       матричные хелперы для signals/
```

Учебные материалы (главы `ch*.py`, `charts/`, ноутбук, исходный пример
`performance.py`) перенесены в `learning/investor_book/` — сервис их не
импортирует.

### Докачка только недостающего

Клиент просит окно `[to - days, to]`. В базе известно `[min, max]`, поэтому
у источника запрашиваются только два куска:

```
[from_ ................. to]
        [min ....... max]

недостающее = (from_ .. min - шаг) + (max .. to)
```

- **начало окна** докачивается, только если дыра больше одного шага — иначе
  получился бы запрос за единственный бар, которого в источнике может не быть
  (ночь, выходной);
- **хвост** перечитывается всегда: последний бар мог ещё не закрыться, и `upsert`
  обновит его.

Всё, что уже в базе, повторно не запрашивается. Пример из логов после
перезапуска контейнера:

```
BBG004730N88/CANDLE_INTERVAL_HOUR: в БД 575 свечей, докачано 1 за 1 диапазон(ов), ответ: tinvest
```

### Таблица `candles`

| Колонка | Тип | Назначение |
|---|---|---|
| `instrument_id`, `interval` | text | часть первичного ключа |
| `time` | timestamptz | часть первичного ключа |
| `open`, `high`, `low`, `close` | numeric(20,9) | точное представление `Quotation` |
| `volume` | bigint | |
| `is_complete` | boolean | флаг закрытия бара |

`PRIMARY KEY (instrument_id, interval, time)` — `upsert` идемпотентен, дублей нет.

Схема создаётся при старте (`CREATE TABLE IF NOT EXISTS`), миграции появятся,
когда таблиц станет больше одной.

## Переменные окружения

| Переменная | По умолчанию | Зачем |
|---|---|---|
| `DATABASE_URL` | — (обязательна) | строка подключения к PostgreSQL |
| `REFRESH_INTERVAL_SECONDS` | `30` | период фонового обновления |
| `WARMUP_INSTRUMENTS` | `BBG004730N88` | что прогреть на старте (через запятую) |
| `WARMUP_INTERVALS` | `CANDLE_INTERVAL_HOUR` | интервалы прогрева |
| `WARMUP_DAYS` | `30` | глубина прогрева |
| `TOKEN` | — | токен T-Invest; без него сервис отдаёт мок |
| `TINVEST_TIMEOUT_SECONDS` | `120` | таймаут одного gRPC-вызова к T-Invest (внутри SDK, по deadline) |

Токен берётся из окружения (в compose — из корневого `.env`) либо из ближайшего
`.env` вверх по дереву при локальном запуске.

## Контракт

`GET /candles?instrument_id=BBG004730N88&interval=CANDLE_INTERVAL_HOUR&days=30`

Ответ — массив `HistoricCandle`: цены как `Quotation { units, nano }`, время ISO 8601,
флаг `isComplete`. Заголовки: `X-Data-Source` (`tinvest` | `postgres` | `mock`),
`X-Candles-Count`.

`GET /health` — `{status, refresh_interval_seconds, refreshes, errors, last_error,
last_fetched, last_source, keys, snapshots}`.

## Аналитика: `/analysis`

`GET /analysis?instrument_id=BBG004730N88&interval=CANDLE_INTERVAL_HOUR&days=30`

Считается поверх тех же свечей, что отдаёт `/candles`: у T-Invest ничего
дополнительно не запрашивается. Заголовки: `X-Data-Source`, `X-Signals-Count`.

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

Почему расчёт на сервере, а не в браузере: правило должно быть одно для UI,
будущего автоброкера и бэктеста. Клиент получает готовые ряды и только рисует.

### Индикаторы

Считаются в `service/analysis.py` по close/high/low окна:

| id | Что это | Панель |
|---|---|---|
| `sma20` | простое скользящее среднее, 20 | цена |
| `ema50` | экспоненциальное, 50 | цена |
| `rsi14` | RSI по Уайлдеру, 14 | отдельная, шкала 0–100 |
| `atr14` | ATR по Уайлдеру, 14 | отдельная, своя шкала |

Точки «прогрева» (пока истории меньше периода) не отдаются — первый элемент
`values` соответствует первой посчитанной свече.

### Паттерны

Модули `signals/*` пришли из песочницы: каждая функция получает матрицу
`[open, high, low, close, buy, sell, atr]` и помечает строки `1` (покупка)
и `-1` (продажа). Реестр и сопоставление аргументов — в `analysis.PATTERNS`,
сейчас подключены все 27 модулей.

Соглашение то же, что было в песочнице: сигнал ставится на **следующий** бар
после подтверждения, то есть вход — по открытию этого бара. Поэтому в ответе
`time` — бар входа, а `price` — его цена открытия.

Один сломанный паттерн не ломает ответ: ошибка попадает в
`patterns[].error`, остальные считаются.

## Производительность: `/performance`

`GET /performance?instrument_id=BBG004730N88&interval=CANDLE_INTERVAL_HOUR&days=30&patterns=tasuki,three_candies`

Бэктест считает `service/performance.py`. Правила перенесены без изменений из
учебного примера `learning/investor_book/util/performance.py` (в проекте он
больше не нужен — сервис его не импортирует):

- вход по цене открытия бара, на котором сработал сигнал;
- выход по открытию следующего сигнала **того же** паттерна в любую сторону;
- результат лонга = `open(выход) − open(вход)`, шорта — наоборот;
- комиссии и проскальзывание не учитываются, стопов нет;
- сигнал без закрывающего сигнала в окне в статистику не попадает
  (в примере такой «хвост» тоже молча терялся).

| Поле | Смысл |
|---|---|
| `signals` | сколько раз паттерн сработал |
| `open_trades` | сигналы, оставшиеся без выхода — в сделки не вошли |
| `trades` | число закрытых сделок |
| `hit_ratio` | доля прибыльных, % |
| `profit_factor` | сумма прибылей / сумма убытков |
| `risk_reward` | средняя прибыль / средний убыток |
| `net_result` | сумма результатов, ₽ на акцию |
| `avg_result`, `best`, `worst` | среднее, лучшая и худшая сделка |

`null` в коэффициентах — «не определено»: делитель нулевой (например, у набора
без убыточных сделок profit factor посчитать нельзя). В примере на этом месте
получался `inf`/`nan`.

Считается поверх тех же сигналов, что отдаёт `/analysis`, поэтому таблица и
отметки на графике всегда совпадают.

### Пересчёт с включёнными и выключенными сигналами

`patterns` — id через запятую. Так клиент пересчитывает таблицу под свой выбор:
без параметра считаются все паттерны окна, с параметром — только перечисленные.
Пустая строка (`patterns=`) — «не выбран ни один»: ответ без строк, но с полным
`available`. Это не то же самое, что отсутствие параметра, поэтому клиент
отправляет пустой список явно.

`available` в ответе всегда содержит **все** сработавшие паттерны: из него
строится список галочек, поэтому он не сужается вместе с выбором.

`total` складывает сделки выбранных паттернов в один набор. Это сумма сигналов,
а не совместная торговля: позиции разных паттернов между собой не согласуются.

## Зависимости

Ради сигналов в `requirements.txt` добавлен `numpy`. `util/data_utils.py`
импортирует MetaTrader5, pandas и pytz **лениво**, только внутри функций,
которым они нужны (`get_quotes`, `mass_import`). Поэтому `signals/*` и
`indicators/*` импортируются в контейнере, где MT5 и matplotlib нет.

## Docker

`Dockerfile` копирует `market/`, `service/`, `signals/`, `indicators/` и `util/`.

SDK `t-tech-investments` ставится из GitLab Package Registry TBank — в PyPI его нет
([документация SDK](https://developer.tbank.ru/invest/sdk/python_sdk/faq_python)):

```
--extra-index-url https://opensource.tbank.ru/api/v4/projects/238/packages/pypi/simple
--trusted-host opensource.tbank.ru
```

Реестр подключён **дополнительным** индексом: сам пакет берётся из GitLab,
его зависимости (`grpcio`, `protobuf`, `requests` и др.) — из PyPI как обычно.

`--trusted-host` нужен потому, что сертификат внутреннего хоста выпущен
корпоративным CA, которого нет в образе. URL и хост вынесены в build-args
`TINVEST_INDEX_URL` и `TINVEST_TRUSTED_HOST` — реестр можно подменить при сборке.

```bash
cd project
docker compose up --build
```
