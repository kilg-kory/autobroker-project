import type { DataPoint } from 'react-candlesticks';
import { quotationToNumber } from '../../api/quotation';
import type { HistoricCandle } from '../../api/types';

/** HistoricCandle (T-Invest) -> DataPoint (react-candlesticks). */
export function toDataPoints(candles: HistoricCandle[]): DataPoint[] {
  return candles.map((candle) => ({
    time: candle.time,
    open: quotationToNumber(candle.open),
    high: quotationToNumber(candle.high),
    low: quotationToNumber(candle.low),
    close: quotationToNumber(candle.close),
    volume: candle.volume,
  }));
}
