/**
 * Типы повторяют ответы T-Invest API (t_tech.invest), чтобы мок и будущий
 * реальный бэкенд остались взаимозаменяемыми.
 *
 * За образец взят вызов из project/investor/tryTAPI.ipynb:
 *
 *   client.get_all_candles(
 *       instrument_id="BBG004730N88",
 *       from_=now() - timedelta(days=365),
 *       interval=CandleInterval.CANDLE_INTERVAL_HOUR,
 *       candle_source_type=CandleSource.CANDLE_SOURCE_UNSPECIFIED,
 *   )
 */

/** Деньги в API передаются как units + nano (10^-9), а не как float. */
export type Quotation = {
  units: number;
  nano: number;
};

/** Одна историческая свеча — аналог HistoricCandle из t_tech.invest. */
export type HistoricCandle = {
  open: Quotation;
  high: Quotation;
  low: Quotation;
  close: Quotation;
  volume: number;
  /** ISO 8601 в UTC */
  time: string;
  isComplete: boolean;
};

export type CandleInterval =
  | 'CANDLE_INTERVAL_MIN_15'
  | 'CANDLE_INTERVAL_HOUR'
  | 'CANDLE_INTERVAL_DAY';

export type GetAllCandlesArgs = {
  /** Тикер в нотации T-Invest, например BBG004730N88 (Сбербанк) */
  instrumentId: string;
  interval?: CandleInterval;
  /** Глубина истории в днях; в ноутбуке запрашивается 365 */
  days?: number;
};

/** Точка индикатора: время свечи и значение. */
export type IndicatorPoint = {
  time: string;
  value: number;
};

/** Ряд индикатора. `panel` говорит, на какой панели графика его рисовать. */
export type IndicatorSeries = {
  id: string;
  title: string;
  panel: 'price' | 'rsi' | 'atr';
  period: number;
  values: IndicatorPoint[];
};

/** Сколько раз паттерн сработал в окне. */
export type PatternInfo = {
  id: string;
  title: string;
  count: number;
  error?: string | null;
};

/** Отметка паттерна: бар входа, направление и цена открытия. */
export type SignalPoint = {
  time: string;
  pattern: string;
  title: string;
  direction: 'buy' | 'sell';
  price: number;
};

/** Ответ GET /api/analysis — аналитика, посчитанная в investor. */
export type AnalysisResponse = {
  instrument_id: string;
  interval: string;
  days: number;
  source: string;
  candles: number;
  indicators: IndicatorSeries[];
  patterns: PatternInfo[];
  signals: SignalPoint[];
};

export type GetAnalysisArgs = GetAllCandlesArgs;

/** Бэктест одного паттерна. `null` в коэффициентах — «не определено». */
export type PerformanceRow = {
  id: string;
  title: string;
  signals: number;
  /** сигналы без закрывающего сигнала в окне — в сделки не вошли */
  open_trades: number;
  trades: number;
  hit_ratio: number | null;
  profit_factor: number | null;
  risk_reward: number | null;
  net_result: number;
  avg_result: number | null;
  best: number | null;
  worst: number | null;
};

/** Итог по выбранным паттернам: сделки всех паттернов в одном наборе. */
export type PerformanceTotal = Omit<PerformanceRow, 'id' | 'title' | 'open_trades'> & {
  patterns: number;
};

/** Паттерн, который срабатывал в окне — из него строится список галочек. */
export type AvailablePattern = {
  id: string;
  title: string;
  signals: number;
};

/** Ответ GET /api/performance. */
export type PerformanceResponse = {
  instrument_id: string;
  interval: string;
  days: number;
  source: string;
  candles: number;
  patterns: PerformanceRow[];
  total: PerformanceTotal;
  available: AvailablePattern[];
};

export type GetPerformanceArgs = GetAllCandlesArgs & {
  /** id паттернов, по которым считать; не задано — все паттерны окна */
  patterns?: string[];
};
