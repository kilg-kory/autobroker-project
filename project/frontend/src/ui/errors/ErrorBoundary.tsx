import { Component, type ErrorInfo, type ReactNode } from 'react';
import Alert from '@mui/material/Alert';
import AlertTitle from '@mui/material/AlertTitle';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

type ErrorBoundaryProps = {
  children: ReactNode;
  /** Что именно сломалось — попадает в заголовок сообщения. */
  title?: string;
};

type ErrorBoundaryState = {
  error: Error | null;
};

/**
 * Ловит ошибки рендера, чтобы одна сломанная карточка не гасила весь дашборд.
 *
 * Без границы любое исключение в дереве React размонтирует всё приложение —
 * в разработке это выглядело как белый экран вместо сообщения об ошибке
 * (например, при дублирующихся id слоёв графика).
 */
export default class ErrorBoundary extends Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // в консоли остаётся стек: он нужен, чтобы разобраться, а не чтобы пугать
    console.error('Ошибка рендера:', error, info.componentStack);
  }

  private reset = (): void => {
    this.setState({ error: null });
  };

  render(): ReactNode {
    const { error } = this.state;
    if (!error) {
      return this.props.children;
    }

    return (
      <Alert
        severity="error"
        sx={{ width: '100%' }}
        action={
          <Button color="inherit" size="small" onClick={this.reset}>
            Повторить
          </Button>
        }
      >
        <AlertTitle>{this.props.title ?? 'Раздел не отрисовался'}</AlertTitle>
        <Stack spacing={0.5}>
          <Typography variant="body2">
            Данные не потеряны — остальные блоки работают. Можно повторить
            попытку или обновить страницу.
          </Typography>
          <Box
            component="pre"
            sx={{
              m: 0,
              fontSize: 12,
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
              opacity: 0.75,
            }}
          >
            {error.message}
          </Box>
        </Stack>
      </Alert>
    );
  }
}
