import { useMemo, useState } from 'react';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Checkbox from '@mui/material/Checkbox';
import CircularProgress from '@mui/material/CircularProgress';
import Divider from '@mui/material/Divider';
import Stack from '@mui/material/Stack';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableFooter from '@mui/material/TableFooter';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import type { CandleInterval, PerformanceRow, PerformanceTotal } from '../../api/types';
import { useGetPerformanceQuery } from '../../api/investorApi';

type PerformanceCardProps = {
  instrumentId: string;
  interval: CandleInterval;
  days: number;
};

const priceFormatter = new Intl.NumberFormat('ru-RU', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const ratioFormatter = new Intl.NumberFormat('ru-RU', {
  minimumFractionDigits: 3,
  maximumFractionDigits: 3,
});

/** `null` — метрика не определена (делитель нулевой), печатаем прочерк. */
function formatMetric(value: number | null): string {
  return value === null || !Number.isFinite(value) ? '—' : priceFormatter.format(value);
}

function formatRatio(value: number | null): string {
  return value === null || !Number.isFinite(value) ? '—' : ratioFormatter.format(value);
}

function formatNet(value: number): string {
  const sign = value > 0 ? '+' : '';
  return `${sign}${priceFormatter.format(value)}`;
}

function netColor(value: number): string {
  if (value > 0) {
    return 'success.main';
  }
  if (value < 0) {
    return 'error.main';
  }
  return 'text.secondary';
}

const oneDecimal = new Intl.NumberFormat('ru-RU', {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});

/**
 * Безубыточный hit ratio для текущего R/R.
 *
 *   p · avgWin = (1 − p) · avgLoss   =>   p = 1 / (1 + avgWin/avgLoss)
 *
 * При R/R = 1 безубыток даёт 50 % попаданий, при 1,5 — 40 %, при 0,5 — 67 %.
 */
function breakEvenHitRatio(riskReward: number): number {
  return riskReward > 0 ? 100 / (1 + riskReward) : 100;
}

function riskRewardNote(row: PerformanceRow): string {
  if (row.risk_reward === null || !Number.isFinite(row.risk_reward)) {
    return '';
  }
  const threshold = breakEvenHitRatio(row.risk_reward);
  const actual = row.hit_ratio;
  const verdict =
    actual === null || !Number.isFinite(actual)
      ? 'попаданий нет'
      : actual >= threshold
        ? 'прибыльно'
        : 'убыточно';

  return (
    `Безубыток при hit ratio ≥ ${oneDecimal.format(threshold)} %, ` +
    `сейчас ${actual === null ? '—' : `${oneDecimal.format(actual)} %`} — ${verdict}`
  );
}

function HintRow({ range, text }: { range: string; text: string }) {
  return (
    <Stack direction="row" spacing={1} sx={{ alignItems: 'baseline' }}>
      <Typography variant="caption" sx={{ minWidth: 64, fontWeight: 600, whiteSpace: 'nowrap' }}>
        {range}
      </Typography>
      <Typography variant="caption">{text}</Typography>
    </Stack>
  );
}

/** Подсказка к столбцу Risk / Reward: как читать значение и где границы. */
function RiskRewardHint() {
  return (
    <Box sx={{ maxWidth: 360 }}>
      <Typography variant="caption" sx={{ fontWeight: 600 }}>
        Средняя прибыльная сделка ÷ средняя убыточная
      </Typography>
      <Typography variant="caption" component="p" sx={{ mt: 0.5 }}>
        Считается по фактическим закрытым сделкам, а не по плану сделки.
      </Typography>

      <Divider sx={{ my: 1, borderColor: 'rgba(255, 255, 255, 0.25)' }} />

      <Stack spacing={0.5}>
        <HintRow range="меньше 1" text="плохо: убыток в среднем больше прибыли" />
        <HintRow range="1 – 1,5" text="рабочее, если попаданий больше 50–60 %" />
        <HintRow range="1,5 – 2,5" text="хорошо" />
        <HintRow range="больше 3" text="настораживает: мало сделок или один крупный выигрыш" />
      </Stack>

      <Divider sx={{ my: 1, borderColor: 'rgba(255, 255, 255, 0.25)' }} />

      <Typography variant="caption" component="p">
        Безубыточный hit ratio = 100 / (1 + R/R): при 1,5 это 40 %, при 0,5 — 67 %.
        Смотрите вместе со «Сделок»: на 10 сделках значение шумное.
      </Typography>
    </Box>
  );
}

/**
 * Таблица производительности паттернов.
 *
 * Метрики повторяют `project/investor/util/performance.py`: вход по открытию
 * бара сигнала, выход по открытию следующего сигнала, без комиссий.
 *
 * Галочки — единственное управление: изменение сразу уходит на сервер
 * (`patterns=id1,id2`), и таблица с итогом пересчитываются под новый набор.
 * Чекбокс в шапке отмечает и снимает все паттерны.
 */
export default function PerformanceCard({
  instrumentId,
  interval,
  days,
}: PerformanceCardProps) {
  // selected === null значит «ещё не трогали»: отмечаем всё, что есть в ответе
  const [selected, setSelected] = useState<string[] | null>(null);

  const { data, isFetching, isError } = useGetPerformanceQuery({
    instrumentId,
    interval,
    days,
    patterns: selected ?? undefined,
  });

  const available = useMemo(() => data?.available ?? [], [data]);
  const availableIds = useMemo(
    () => available.map((pattern) => pattern.id),
    [available],
  );

  const rows = useMemo(() => data?.patterns ?? [], [data]);
  const total: PerformanceTotal | undefined = data?.total;

  /**
   * Строки таблицы — все сработавшие паттерны, а не только посчитанные.
   *
   * Сервер возвращает лишь отмеченные паттерны, поэтому снятый паттерн
   * исчезал бы вместе с галочкой. Поэтому непосчитанные строки остаются
   * внизу с прочерками — их можно снова отметить.
   */
  const tableRows = useMemo(() => {
    const computedById = new Map(rows.map((row) => [row.id, row]));
    return [
      ...rows.map((row) => ({
        id: row.id,
        title: row.title,
        signals: row.signals,
        row: row as PerformanceRow | undefined,
      })),
      ...available
        .filter((pattern) => !computedById.has(pattern.id))
        .map((pattern) => ({
          id: pattern.id,
          title: pattern.title,
          signals: pattern.signals,
          row: undefined as PerformanceRow | undefined,
        })),
    ];
  }, [rows, available]);

  const checked = selected ?? availableIds;
  const allChecked = availableIds.length > 0 && checked.length === availableIds.length;
  const nothingChecked = checked.length === 0;

  const toggle = (id: string) => {
    setSelected(
      checked.includes(id) ? checked.filter((item) => item !== id) : [...checked, id],
    );
  };

  const toggleAll = () => {
    setSelected(allChecked ? [] : availableIds);
  };

  return (
    <Card variant="outlined">
      <CardContent>
        <Stack direction="row" spacing={1} sx={{ alignItems: 'center', mb: 1 }}>
          <Typography component="h2" variant="subtitle2">
            Производительность паттернов
          </Typography>
          {isFetching && <CircularProgress size={14} />}
        </Stack>

        <Typography variant="caption" color="text.secondary">
          Вход по открытию бара сигнала, выход — по следующему сигналу паттерна.
          Комиссии и стопы не учитываются, незакрытые сигналы в статистику не входят.
          Пересчитывается сразу после изменения галочек.
        </Typography>

        {isError && (
          <Alert severity="warning" sx={{ mt: 2 }}>
            Бэктест недоступен: investor не ответил.
          </Alert>
        )}

        {!isError && nothingChecked && (
          <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
            Ни один паттерн не отмечен — отметьте хотя бы один, чтобы посчитать
            производительность.
          </Typography>
        )}

        {!isError && tableRows.length > 0 && (
          <TableContainer sx={{ mt: 1 }}>
            <Table size="small" sx={{ whiteSpace: 'nowrap' }}>
              <TableHead>
                <TableRow>
                  <TableCell padding="checkbox">
                    <Checkbox
                      size="small"
                      checked={allChecked}
                      indeterminate={!allChecked && !nothingChecked}
                      onChange={toggleAll}
                      disabled={availableIds.length === 0}
                      slotProps={{ input: { 'aria-label': 'Отметить все паттерны' } }}
                    />
                  </TableCell>
                  <TableCell>Паттерн</TableCell>
                  <TableCell align="right">Сигналов</TableCell>
                  <TableCell align="right">Сделок</TableCell>
                  <TableCell align="right">Hit ratio</TableCell>
                  <TableCell align="right">Profit factor</TableCell>
                  <TableCell align="right">
                    <Tooltip arrow placement="top-end" title={<RiskRewardHint />}>
                      <Stack
                        component="span"
                        direction="row"
                        spacing={0.5}
                        sx={{
                          alignItems: 'center',
                          justifyContent: 'flex-end',
                          cursor: 'help',
                        }}
                      >
                        <span>Risk / Reward</span>
                        <InfoOutlinedIcon sx={{ fontSize: 14, color: 'text.disabled' }} />
                      </Stack>
                    </Tooltip>
                  </TableCell>
                  <TableCell align="right">Итог, ₽</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {tableRows.map(({ id, title, signals, row }) => (
                  <TableRow key={id} hover sx={row ? undefined : { opacity: 0.55 }}>
                    <TableCell padding="checkbox">
                      <Checkbox
                        size="small"
                        checked={checked.includes(id)}
                        onChange={() => toggle(id)}
                        slotProps={{ input: { 'aria-label': `Включить ${title}` } }}
                      />
                    </TableCell>
                    <TableCell>{title}</TableCell>
                    <TableCell align="right">{signals}</TableCell>
                    <TableCell align="right">{row ? row.trades : '—'}</TableCell>
                    <TableCell align="right">
                      {row ? `${formatMetric(row.hit_ratio)} %` : '—'}
                    </TableCell>
                    <TableCell align="right">
                      {row ? formatMetric(row.profit_factor) : '—'}
                    </TableCell>
                    <TableCell align="right">
                      {row && row.risk_reward !== null ? (
                        <Tooltip arrow title={riskRewardNote(row)}>
                          <Box
                            component="span"
                            sx={{
                              cursor: 'help',
                              borderBottom: '1px dotted',
                              borderColor: 'divider',
                            }}
                          >
                            {formatRatio(row.risk_reward)}
                          </Box>
                        </Tooltip>
                      ) : (
                        formatRatio(row?.risk_reward ?? null)
                      )}
                    </TableCell>
                    <TableCell
                      align="right"
                      sx={
                        row
                          ? { color: netColor(row.net_result), fontWeight: 600 }
                          : undefined
                      }
                    >
                      {row ? formatNet(row.net_result) : '—'}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
              {total && total.patterns > 0 && (
                <TableFooter>
                  <TableRow>
                    <TableCell />
                    <TableCell>Итого · {total.patterns} паттерн(ов)</TableCell>
                    <TableCell align="right">{total.signals}</TableCell>
                    <TableCell align="right">{total.trades}</TableCell>
                    <TableCell align="right">{formatMetric(total.hit_ratio)} %</TableCell>
                    <TableCell align="right">{formatMetric(total.profit_factor)}</TableCell>
                    <TableCell align="right">{formatRatio(total.risk_reward)}</TableCell>
                    <TableCell
                      align="right"
                      sx={{ color: netColor(total.net_result), fontWeight: 700 }}
                    >
                      {formatNet(total.net_result)}
                    </TableCell>
                  </TableRow>
                </TableFooter>
              )}
            </Table>
          </TableContainer>
        )}

        <Box sx={{ mt: 1 }}>
          <Typography variant="caption" color="text.secondary">
            Итог складывает сделки всех отмеченных паттернов в один набор — он
            показывает сумму сигналов, а не совместную торговлю.
          </Typography>
        </Box>
      </CardContent>
    </Card>
  );
}
