import { defineLayer, drawLineSeries, parseLineConfig } from 'react-candlesticks';
import type {
  BaseLayerConfig,
  BaseLayerConfigComplete,
  LayerCalculate,
  LayerDraw,
  ScaleRange,
} from 'react-candlesticks';

/**
 * Слои графика для аналитики из investor.
 *
 * Библиотека считает свои индикаторы сама, но у нас значения уже посчитаны
 * на сервере — чтобы правило было одно для UI, автоброкера и бэктеста.
 * Поэтому здесь два «проводниковых» слоя: они берут готовые ряды из конфига
 * и только рисуют их.
 *
 * Тонкость: индексы баров и индексов свечей в библиотеке не совпадают —
 * бары строятся по торговым сессиям, и в выходные барам не соответствует
 * ни одна свеча (в `dataIndexByBar` там -1). Поэтому значения из API
 * раскладываются по барам через счётчик свечей, а не по прямому индексу.
 */

export type SeriesPoint = { time: string; value: number };

type AnalysisLineConfig = BaseLayerConfig & {
  /** Ряд из investor, по точке на свечу, без пропусков на «прогреве». */
  points?: SeriesPoint[];
  color?: string;
  width?: number;
  /** Подпись панели и текущего значения (RSI 14 · 62.3). */
  label?: string;
  /** Горизонтальные ориентиры: у RSI это 30 и 70. */
  referenceLines?: number[];
};

type AnalysisLineComplete = BaseLayerConfigComplete & {
  points: SeriesPoint[];
  color: string;
  width: number;
  label: string;
  referenceLines: number[];
};

const priceValueToY =
  (min: number, max: number, top: number, height: number) =>
  (value: number) => {
    const span = max - min;
    return span === 0 ? top + height / 2 : top + ((max - value) / span) * height;
  };

/** Раскладывает точки API по барам: свеча -> её порядковый номер -> бар. */
const placeOnBars: LayerCalculate<AnalysisLineComplete> = (
  config,
  inputs,
  outputs,
  startBarIndex,
  endBarIndex,
) => {
  const prices = inputs.input.values;
  const points = config.points;
  let candle = 0;

  for (let bar = 0; bar < endBarIndex; bar++) {
    // NaN — бар без свечи (ночь, выходной): пропускаем, номер свечи не растёт
    if (!Number.isFinite(prices[bar])) {
      continue;
    }
    if (bar >= startBarIndex) {
      const point = points[candle];
      if (point && Number.isFinite(point.value)) {
        outputs.value[bar] = point.value;
      }
    }
    candle += 1;
  }
};

function createLineLayer(
  type: string,
  defaultScale: { key: string; domain: 'price' | 'value'; range: ScaleRange },
  includeInAutoScale: boolean,
) {
  const draw: LayerDraw<AnalysisLineComplete> = (
    context,
    _axesContext,
    _chartConfig,
    _panelConfig,
    config,
    _layout,
    viewportData,
    _chartMetrics,
    panelMetrics,
    layerMetrics,
  ) => {
    const values = viewportData.layersData.layerDataInstances[config.id]?.outputValues
      ?.value as Float64Array | undefined;
    const lineConfig = parseLineConfig({ color: config.color, width: config.width });
    if (!lineConfig) {
      return;
    }

    const { startBarIndex, endBarIndex, metadata } = viewportData.timeScale;
    // правый край области данных — от него отсчитываем подпись панели
    const rightEdge = endBarIndex * metadata.intervalSize - metadata.scrollOffset;

    context.save();
    for (const reference of config.referenceLines) {
      const y = Math.round(layerMetrics.valueToY(reference));
      if (y < panelMetrics.paddedTopPx || y > panelMetrics.paddedBottomPx) {
        continue;
      }
      context.strokeStyle = config.color;
      context.globalAlpha = 0.35;
      context.lineWidth = 1;
      context.setLineDash([4, 4]);
      context.beginPath();
      context.moveTo(0, y);
      context.lineTo(rightEdge, y);
      context.stroke();
    }
    context.restore();

    if (values) {
      drawLineSeries({
        context,
        values,
        lineConfig,
        valueToY: layerMetrics.valueToY,
        startBarIndex,
        endBarIndex,
        intervalSize: metadata.intervalSize,
        scrollOffset: metadata.scrollOffset,
      });
    }

    // Подпись панели: у своих слоёв нет легенды библиотеки, поэтому пишем сами.
    if (config.label) {
      let last: number | undefined;
      for (let bar = endBarIndex; bar >= startBarIndex; bar--) {
        const value = values?.[bar];
        if (value !== undefined && Number.isFinite(value)) {
          last = value;
          break;
        }
      }
      const text = last === undefined ? config.label : `${config.label} · ${last.toFixed(2)}`;
      context.save();
      context.font = '12px system-ui, -apple-system, Segoe UI, Roboto, sans-serif';
      context.fillStyle = config.color;
      context.textAlign = 'right';
      context.textBaseline = 'top';
      context.fillText(text, rightEdge, panelMetrics.paddedTopPx + 4);
      context.restore();
    }
  };

  return defineLayer<AnalysisLineConfig, AnalysisLineComplete>({
    type,
    displayName: `${type} layer`,
    parseConfig: (config, _theme, panelId) => ({
      id: config.id ?? `${type}_${panelId}`,
      type,
      indicator: true,
      defaultScale,
      scale: config.scale ?? null,
      scalePolicy: 'derived',
      valueToY: config.valueToY ?? priceValueToY,
      legend: null,
      yAxis: null,
      valueLabelFormatter: (value: number) => value.toFixed(2),
      requiredInputKeys: ['input'],
      inputs: config.inputs ?? [{ key: 'input', source: { type: 'price', field: 'close' } }],
      outputs: ['value'],
      period: 1,
      offset: 0,
      lookback: 0,
      calculate: true,
      includeInAutoScale,
      points: config.points ?? [],
      color: config.color ?? '#8b5cf6',
      width: config.width ?? 1.5,
      label: config.label ?? '',
      referenceLines: config.referenceLines ?? [],
    }),
    calculate: placeOnBars,
    draw,
  });
}

/** SMA/EMA поверх свечей — делят ценовую шкалу с `Candlesticks`. */
export const priceLineLayer = createLineLayer(
  'custom:analysis-price',
  { key: 'price_auto', domain: 'price', range: { type: 'auto' } },
  false,
);

/** RSI в отдельной панели: жёсткая шкала 0–100 и ориентиры 30/70. */
export const rsiLayer = createLineLayer(
  'custom:analysis-rsi',
  {
    key: 'value_bounded_0_100',
    domain: 'value',
    range: { type: 'bounded', min: 0, max: 100 },
  },
  true,
);

/** ATR в отдельной панели: своя автоматическая шкала, диапазон задаёт сам ряд. */
export const atrLayer = createLineLayer(
  'custom:analysis-atr',
  { key: 'value_auto', domain: 'value', range: { type: 'auto' } },
  true,
);

export const analysisLineDefinitions = [priceLineLayer, rsiLayer, atrLayer] as const;

// --------------------------------------------------------------------------
// Отметки сигналов
// --------------------------------------------------------------------------

export type ChartSignal = {
  time: string;
  direction: 'buy' | 'sell';
  title: string;
};

type SignalMarkersConfig = BaseLayerConfig & {
  signals?: ChartSignal[];
};

type SignalMarkersComplete = BaseLayerConfigComplete & {
  signals: ChartSignal[];
};

const BUY_COLOR = '#16a34a';
const SELL_COLOR = '#dc2626';
const MARKER_SIZE = 7;

const drawMarkers: LayerDraw<SignalMarkersComplete> = (
  context,
  _axesContext,
  _chartConfig,
  _panelConfig,
  config,
  _layout,
  viewportData,
  _chartMetrics,
  _panelMetrics,
  layerMetrics,
) => {
  const { startBarIndex, endBarIndex, metadata } = viewportData.timeScale;
  const { intervalSize, scrollOffset } = metadata;
  const { timestamp, high, low } = viewportData.dataMap.ohlcvs;

  // время в мс -> сигналы на этом баре
  const byTime = new Map<number, ChartSignal[]>();
  for (const signal of config.signals) {
    const key = Date.parse(signal.time);
    const list = byTime.get(key);
    if (list) {
      list.push(signal);
    } else {
      byTime.set(key, [signal]);
    }
  }
  if (byTime.size === 0) {
    return;
  }

  const half = intervalSize / 2;

  for (let bar = startBarIndex; bar <= endBarIndex; bar++) {
    const ts = timestamp[bar];
    if (!Number.isFinite(ts)) {
      continue;
    }
    const signals = byTime.get(ts);
    if (!signals) {
      continue;
    }

    const x = bar * intervalSize - scrollOffset + half;
    const barHigh = high[bar];
    const barLow = low[bar];

    signals.forEach((signal, index) => {
      const isBuy = signal.direction === 'buy';
      // отметки не перекрываются, если на баре сработало несколько паттернов
      const shift = index * (MARKER_SIZE + 2);
      const anchor = isBuy
        ? layerMetrics.valueToY(barLow) + MARKER_SIZE + shift
        : layerMetrics.valueToY(barHigh) - MARKER_SIZE - shift;

      context.save();
      context.fillStyle = isBuy ? BUY_COLOR : SELL_COLOR;
      context.beginPath();
      if (isBuy) {
        context.moveTo(x, anchor - MARKER_SIZE);
        context.lineTo(x - MARKER_SIZE / 1.6, anchor + MARKER_SIZE / 2);
        context.lineTo(x + MARKER_SIZE / 1.6, anchor + MARKER_SIZE / 2);
      } else {
        context.moveTo(x, anchor + MARKER_SIZE);
        context.lineTo(x - MARKER_SIZE / 1.6, anchor - MARKER_SIZE / 2);
        context.lineTo(x + MARKER_SIZE / 1.6, anchor - MARKER_SIZE / 2);
      }
      context.closePath();
      context.fill();
      context.restore();
    });
  }
};

const signalMarkersDefinition = defineLayer<SignalMarkersConfig, SignalMarkersComplete>({
  type: 'custom:analysis-signals',
  displayName: 'Signal markers',
  parseConfig: (config, _theme, panelId) => ({
    id: config.id ?? `analysis-signals_${panelId}`,
    type: 'custom:analysis-signals',
    indicator: true,
    defaultScale: { key: 'price_auto', domain: 'price', range: { type: 'auto' } },
    scale: config.scale ?? null,
    scalePolicy: 'derived',
    valueToY: config.valueToY ?? priceValueToY,
    legend: null,
    yAxis: null,
    valueLabelFormatter: String,
    requiredInputKeys: ['input'],
    inputs: config.inputs ?? [{ key: 'input', source: { type: 'price', field: 'close' } }],
    outputs: ['value'],
    period: 1,
    offset: 0,
    lookback: 0,
    calculate: true,
    includeInAutoScale: false,
    signals: config.signals ?? [],
  }),
  draw: drawMarkers,
});

export const SignalMarkers = signalMarkersDefinition.Component;
export const signalMarkersDefinitionForChart = signalMarkersDefinition;

export const PriceLine = priceLineLayer.Component;
export const RsiLine = rsiLayer.Component;
export const AtrLine = atrLayer.Component;
