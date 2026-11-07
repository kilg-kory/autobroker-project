import Box from '@mui/material/Box';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Chip from '@mui/material/Chip';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import type { PatternInfo, SignalPoint } from '../../api/types';

type SignalsCardProps = {
  signals: SignalPoint[];
  patterns: PatternInfo[];
  loading?: boolean;
};

const timeFormatter = new Intl.DateTimeFormat('ru-RU', {
  day: '2-digit',
  month: 'short',
  hour: '2-digit',
  minute: '2-digit',
});

/**
 * Список последних сигналов и статистика по паттернам.
 *
 * На графике отметки видны только в пределах прокрутки, поэтому текстовый
 * список рядом: что сработало, когда и в какую сторону.
 */
export default function SignalsCard({ signals, patterns, loading = false }: SignalsCardProps) {
  const latest = [...signals].reverse().slice(0, 8);
  const active = patterns.filter((pattern) => pattern.count > 0);
  const total = signals.length;

  return (
    <Card variant="outlined">
      <CardContent>
        <Stack
          direction="row"
          sx={{ justifyContent: 'space-between', alignItems: 'center', mb: 1 }}
          spacing={1}
        >
          <Typography component="h2" variant="subtitle2">
            Сигналы паттернов
          </Typography>
          <Chip size="small" variant="outlined" label={`${total} за период`} />
        </Stack>

        {loading && (
          <Typography variant="body2" color="text.secondary">
            Считаем паттерны…
          </Typography>
        )}

        {!loading && latest.length === 0 && (
          <Typography variant="body2" color="text.secondary">
            За это окно паттерны не срабатывали.
          </Typography>
        )}

        <Stack spacing={1}>
          {latest.map((signal, index) => (
            <Stack
              key={`${signal.time}-${signal.pattern}-${signal.direction}-${index}`}
              direction="row"
              spacing={1}
              sx={{ alignItems: 'center', justifyContent: 'space-between' }}
            >
              <Stack direction="row" spacing={1} sx={{ alignItems: 'center', minWidth: 0 }}>
                <Chip
                  size="small"
                  color={signal.direction === 'buy' ? 'success' : 'error'}
                  label={signal.direction === 'buy' ? 'покупка' : 'продажа'}
                />
                <Typography variant="body2" noWrap>
                  {signal.title}
                </Typography>
              </Stack>
              <Typography variant="caption" color="text.secondary" sx={{ whiteSpace: 'nowrap' }}>
                {timeFormatter.format(new Date(signal.time))} · {signal.price.toFixed(2)} ₽
              </Typography>
            </Stack>
          ))}
        </Stack>

        {active.length > 0 && (
          <Box sx={{ mt: 2 }}>
            <Typography variant="caption" color="text.secondary">
              Сработавшие паттерны
            </Typography>
            <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap', gap: 1, mt: 1 }}>
              {active
                .sort((left, right) => right.count - left.count)
                .slice(0, 6)
                .map((pattern) => (
                  <Chip
                    key={pattern.id}
                    size="small"
                    variant="outlined"
                    label={`${pattern.title} · ${pattern.count}`}
                  />
                ))}
            </Stack>
          </Box>
        )}
      </CardContent>
    </Card>
  );
}
