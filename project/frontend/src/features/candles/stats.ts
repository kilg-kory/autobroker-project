import type { DataPoint } from 'react-candlesticks';

export type StatItem = {
  title: string;
  value: string;
  interval: string;
  trend: 'up' | 'down' | 'neutral';
  data: number[];
};

const priceFormatter = new Intl.NumberFormat('ru-RU', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const compactFormatter = new Intl.NumberFormat('ru-RU', {
  notation: 'compact',
  maximumFractionDigits: 1,
});

function trendOf(delta: number): StatItem['trend'] {
  if (delta > 0.05) {
    return 'up';
  }
  if (delta < -0.05) {
    return 'down';
  }
  return 'neutral';
}

/** Метрики для карточек сверху считаются из тех же свечей, что и график. */
export function buildStats(points: DataPoint[]): StatItem[] {
  if (points.length === 0) {
    return [];
  }

  const last = points[points.length - 1];
  const previous = points[points.length - 2] ?? last;
  const tail = points.slice(-24);

  const changePercent =
    previous.close === 0 ? 0 : ((last.close - previous.close) / previous.close) * 100;
  const periodHigh = Math.max(...points.map((point) => point.high));
  const periodLow = Math.min(...points.map((point) => point.low));

  return [
    {
      title: 'Последняя цена',
      value: `${priceFormatter.format(last.close)} ₽`,
      interval: `закрытие ${new Date(last.time).toLocaleString('ru-RU')}`,
      trend: trendOf(changePercent),
      data: tail.map((point) => point.close),
    },
    {
      title: 'Изменение за свечу',
      value: `${changePercent >= 0 ? '+' : ''}${changePercent.toFixed(2)} %`,
      interval: `${priceFormatter.format(previous.close)} → ${priceFormatter.format(last.close)} ₽`,
      trend: trendOf(changePercent),
      data: tail.map((point) => point.close),
    },
    {
      title: 'Объём',
      value: compactFormatter.format(last.volume),
      interval: 'контрактов за последнюю свечу',
      trend: trendOf(last.volume - previous.volume),
      data: tail.map((point) => point.volume),
    },
    {
      title: 'Диапазон',
      value: `${priceFormatter.format(periodLow)}–${priceFormatter.format(periodHigh)}`,
      interval: 'мин. и макс. за период, ₽',
      trend: 'neutral',
      data: tail.map((point) => point.high),
    },
  ];
}
