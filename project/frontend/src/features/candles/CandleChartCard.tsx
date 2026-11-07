import { useMemo, useState } from 'react';
import { useColorScheme } from '@mui/material/styles';
import Box from '@mui/material/Box';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Chip from '@mui/material/Chip';
import FormControlLabel from '@mui/material/FormControlLabel';
import Skeleton from '@mui/material/Skeleton';
import Stack from '@mui/material/Stack';
import Switch from '@mui/material/Switch';
import Typography from '@mui/material/Typography';
import { Candlesticks, Chart, Panel } from 'react-candlesticks';
import type { DataPoint } from 'react-candlesticks';
import 'react-candlesticks/style.css';
import type { IndicatorSeries, SignalPoint } from '../../api/types';
import {
  AtrLine,
  PriceLine,
  RsiLine,
  SignalMarkers,
  analysisLineDefinitions,
  signalMarkersDefinitionForChart,
} from '../analysis/analysisLayers';

type ChartGranularity = 'm15' | 'h1' | 'd1';

/** Часовой пояс пользователя, чтобы подписи совпадали с его локальным временем. */
const TIME_ZONE = Intl.DateTimeFormat().resolvedOptions().timeZone;

type TimeLabelArgs = {
  utcTs: number;
  timeUnit: string;
  kind: string;
  timeZoneId?: string | null;
};

const isDateUnit = (unit: string) =>
  unit === 'day' || unit === 'week' || unit === 'month' || unit === 'year';

/**
 * Подписи оси времени по-русски: часы «16:00», дни «23 окт.».
 * Библиотека по умолчанию печатает американский MM/DD и локаль не учитывает.
 */
function formatTimeLabel({ utcTs, timeUnit, kind, timeZoneId }: TimeLabelArgs): string {
  const date = new Date(utcTs);
  const zone = timeZoneId ?? TIME_ZONE;

  if (kind === 'major' || isDateUnit(timeUnit)) {
    return date.toLocaleDateString('ru-RU', {
      day: 'numeric',
      month: 'short',
      timeZone: zone,
    });
  }

  return date.toLocaleTimeString('ru-RU', {
    hour: '2-digit',
    minute: '2-digit',
    timeZone: zone,
  });
}

const PRICE_COLORS = ['#f59e0b', '#3b82f6'];

type CandleChartCardProps = {
  points: DataPoint[];
  signals?: SignalPoint[];
  indicators?: IndicatorSeries[];
  loading?: boolean;
  granularity?: ChartGranularity;
  chartHeight?: number;
};

export default function CandleChartCard({
  points,
  signals = [],
  indicators = [],
  loading = false,
  granularity = 'h1',
  chartHeight = 520,
}: CandleChartCardProps) {
  // MUI 9 работает через CSS-переменные, поэтому theme.palette.mode не отражает
  // выбранную схему — актуальный режим берём из useColorScheme.
  const { mode, systemMode } = useColorScheme();
  const isDark = (mode === 'system' ? systemMode : mode) === 'dark';
  const last = points.length > 0 ? points[points.length - 1] : undefined;

  // Слои аналитики включаются независимо: индикаторы и отметки — разная информация.
  const [showIndicators, setShowIndicators] = useState(true);
  const [showSignals, setShowSignals] = useState(true);

  const priceSeries = indicators.filter((indicator) => indicator.panel === 'price');
  const rsiSeries = indicators.find((indicator) => indicator.id === 'rsi14');
  const atrSeries = indicators.find((indicator) => indicator.id === 'atr14');

  const chartSignals = useMemo(
    () =>
      signals.map((signal) => ({
        time: signal.time,
        direction: signal.direction,
        title: signal.title,
      })),
    [signals],
  );

  const layerDefinitions = useMemo(
    () => [signalMarkersDefinitionForChart, ...analysisLineDefinitions],
    [],
  );

  return (
    <Card variant="outlined">
      <CardContent>
        <Stack
          direction="row"
          sx={{ justifyContent: 'space-between', alignItems: 'center', mb: 1 }}
          spacing={1}
        >
          <Typography component="h2" variant="subtitle2">
            Свечи
          </Typography>
          <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
            <FormControlLabel
              control={
                <Switch
                  size="small"
                  checked={showIndicators}
                  onChange={(event) => setShowIndicators(event.target.checked)}
                />
              }
              label={<Typography variant="caption">Индикаторы</Typography>}
              sx={{ mr: 0 }}
            />
            <FormControlLabel
              control={
                <Switch
                  size="small"
                  checked={showSignals}
                  onChange={(event) => setShowSignals(event.target.checked)}
                />
              }
              label={<Typography variant="caption">Сигналы</Typography>}
              sx={{ mr: 0 }}
            />
            {last && (
              <Chip
                size="small"
                variant="outlined"
                label={`${last.close.toFixed(2)} ₽`}
              />
            )}
          </Stack>
        </Stack>

        {loading || !last ? (
          <Skeleton variant="rounded" height={chartHeight} />
        ) : (
          <Box sx={{ width: '100%' }}>
            <Chart
              data={points}
              granularity={granularity}
              theme={isDark ? 'dark' : 'light'}
              width="auto"
              height={chartHeight}
              initialScrollToLatest
              layerDefinitions={layerDefinitions}
              xAxis={{
                timeZoneId: TIME_ZONE,
                minorLabels: { formatter: formatTimeLabel },
                majorLabels: { formatter: formatTimeLabel },
              }}
            >
              <Panel heightRatio={3}>
                <Candlesticks legend={false} />
                {showIndicators &&
                  priceSeries.map((series, index) => (
                    <PriceLine
                      key={series.id}
                      id={`price-${series.id}`}
                      points={series.values}
                      color={PRICE_COLORS[index % PRICE_COLORS.length]}
                      width={1.5}
                    />
                  ))}
                {showSignals && (
                  <SignalMarkers id="signal-markers" signals={chartSignals} />
                )}
              </Panel>
              {showIndicators && rsiSeries && (
                <Panel heightRatio={1}>
                  <RsiLine
                    id="rsi-line"
                    points={rsiSeries.values}
                    color="#8b5cf6"
                    width={1.5}
                    label="RSI 14"
                    referenceLines={[30, 70]}
                  />
                </Panel>
              )}
              {showIndicators && atrSeries && (
                <Panel heightRatio={1}>
                  <AtrLine
                    id="atr-line"
                    points={atrSeries.values}
                    color="#0ea5e9"
                    width={1.5}
                    label="ATR 14"
                  />
                </Panel>
              )}
            </Chart>
          </Box>
        )}
      </CardContent>
    </Card>
  );
}
