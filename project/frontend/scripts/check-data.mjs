/**
 * Проверка слоя данных без браузера и без сети: HistoricCandle[] -> DataPoint[] -> карточки.
 * Запускается через Vite SSR, поэтому TS и импорты без расширений разрешаются как в сборке.
 *
 *   node scripts/check-data.mjs
 */
import { createServer } from 'vite';

const NANO = 1_000_000_000;

/** Детерминированный ряд в форме ответа backend (HistoricCandle). */
function makeCandles(count = 200, seed = 20261) {
  let state = seed;
  const random = () => {
    state |= 0;
    state = (state + 0x6d2b79f5) | 0;
    let t = Math.imul(state ^ (state >>> 15), 1 | state);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4_294_967_296;
  };
  const quote = (value) => {
    const scaled = Math.round(value * NANO);
    return { units: Math.trunc(scaled / NANO), nano: scaled % NANO };
  };

  let price = 300;
  const start = Date.UTC(2026, 9, 1, 7, 0, 0);
  return Array.from({ length: count }, (_, index) => {
    const open = price;
    const close = Math.max(1, open * (1 + (random() - 0.5) * 0.004));
    const wick = open * (0.0005 + random() * 0.0015);
    price = close;
    return {
      open: quote(open),
      high: quote(Math.max(open, close) + wick * random()),
      low: quote(Math.min(open, close) - wick * random()),
      close: quote(close),
      volume: Math.round(5_000 + random() * 95_000),
      time: new Date(start + index * 3_600_000).toISOString(),
      isComplete: true,
    };
  });
}

const server = await createServer({
  server: { middlewareMode: true },
  appType: 'custom',
  logLevel: 'error',
});

try {
  const { toDataPoints } = await server.ssrLoadModule('/src/features/candles/toDataPoints.ts');
  const { buildStats } = await server.ssrLoadModule('/src/features/candles/stats.ts');

  const candles = makeCandles();
  console.log(`candles: ${candles.length}`);
  console.log(`first:   ${JSON.stringify(candles[0])}`);

  const points = toDataPoints(candles);
  if (points.length !== candles.length) throw new Error('toDataPoints потерял точки');
  console.log(`points:  ${points.length}, last ${JSON.stringify(points.at(-1))}`);

  const stats = buildStats(points);
  if (stats.length !== 4) throw new Error(`ожидалось 4 карточки, получено ${stats.length}`);
  for (const stat of stats) {
    console.log(`  ${stat.title}: ${stat.value} [${stat.trend}]`);
  }

  for (const point of points) {
    if (!(point.high >= point.low)) throw new Error(`high < low: ${JSON.stringify(point)}`);
    if (!(point.high >= point.close && point.high >= point.open)) {
      throw new Error(`high ниже тела: ${JSON.stringify(point)}`);
    }
    if (!(point.low <= point.close && point.low <= point.open)) {
      throw new Error(`low выше тела: ${JSON.stringify(point)}`);
    }
    if (Number.isNaN(new Date(point.time).getTime())) {
      throw new Error(`время не парсится: ${point.time}`);
    }
    if (!Number.isInteger(point.volume) || point.volume <= 0) {
      throw new Error(`объём: ${point.volume}`);
    }
  }

  const again = toDataPoints(makeCandles());
  if (JSON.stringify(again.map((p) => p.close)) !== JSON.stringify(points.map((p) => p.close))) {
    throw new Error('ряд не детерминирован');
  }

  console.log('\nDATA OK');
} finally {
  await server.close();
}
