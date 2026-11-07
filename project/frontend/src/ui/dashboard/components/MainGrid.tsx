import { useMemo } from 'react';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Grid from '@mui/material/Grid';
import Skeleton from '@mui/material/Skeleton';
import Typography from '@mui/material/Typography';
import StatCard from './StatCard';
import CandleChartCard from '../../../features/candles/CandleChartCard';
import SignalsCard from '../../../features/analysis/SignalsCard';
import PerformanceCard from '../../../features/analysis/PerformanceCard';
import { buildStats } from '../../../features/candles/stats';
import { toDataPoints } from '../../../features/candles/toDataPoints';
import { useGetAllCandlesQuery, useGetAnalysisQuery } from '../../../api/investorApi';

/** Инструмент из примера в project/investor/tryTAPI.ipynb — Сбербанк. */
const INSTRUMENT_ID = 'BBG004730N88';
const HISTORY_DAYS = 30;
const QUERY = {
  instrumentId: INSTRUMENT_ID,
  interval: 'CANDLE_INTERVAL_HOUR',
  days: HISTORY_DAYS,
} as const;

export default function MainGrid() {
  const { data: candles, isLoading, isError } = useGetAllCandlesQuery(QUERY);
  const {
    data: analysis,
    isLoading: isAnalysisLoading,
    isError: isAnalysisError,
  } = useGetAnalysisQuery(QUERY);

  const points = useMemo(() => (candles ? toDataPoints(candles) : []), [candles]);
  const stats = useMemo(
    () => (points.length > 0 ? buildStats(points) : []),
    [points],
  );

  return (
    <Box sx={{ width: '100%', maxWidth: { sm: '100%', md: '1700px' } }}>
      <Typography component="h2" variant="h6" sx={{ mb: 2 }}>
        Сбербанк · {INSTRUMENT_ID}
      </Typography>

      {isError && (
        <Alert severity="error" sx={{ mb: 2 }}>
          Не удалось загрузить свечи. Проверьте, что подняты investor и backend.
        </Alert>
      )}

      {isAnalysisError && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          Аналитика недоступна: свечи на графике есть, индикаторы и сигналы — нет.
        </Alert>
      )}

      <Grid container spacing={2} columns={12}>
        {isLoading
          ? [0, 1, 2, 3].map((index) => (
              <Grid key={index} size={{ xs: 12, sm: 6, lg: 3 }}>
                <Skeleton variant="rounded" height={148} />
              </Grid>
            ))
          : stats.map((stat) => (
              <Grid key={stat.title} size={{ xs: 12, sm: 6, lg: 3 }}>
                <StatCard {...stat} />
              </Grid>
            ))}

        <Grid size={{ xs: 12, lg: 8 }}>
          <CandleChartCard
            points={points}
            signals={analysis?.signals}
            indicators={analysis?.indicators}
            loading={isLoading}
          />
        </Grid>

        <Grid size={{ xs: 12, lg: 4 }}>
          <SignalsCard
            signals={analysis?.signals ?? []}
            patterns={analysis?.patterns ?? []}
            loading={isAnalysisLoading}
          />
        </Grid>

        <Grid size={{ xs: 12 }}>
          <PerformanceCard
            instrumentId={QUERY.instrumentId}
            interval={QUERY.interval}
            days={QUERY.days}
          />
        </Grid>
      </Grid>
    </Box>
  );
}
