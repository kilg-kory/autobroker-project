import { alpha } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import Box from '@mui/material/Box';
import Stack from '@mui/material/Stack';
import AppNavbar from './components/AppNavbar';
import Header from './components/Header';
import MainGrid from './components/MainGrid';
import SideMenu from './components/SideMenu';
import Copyright from './internals/components/Copyright';
import AppTheme from '../shared-theme/AppTheme';

export default function Dashboard(props: { disableCustomTheme?: boolean }) {
  return (
    <AppTheme {...props}>
      <CssBaseline enableColorScheme />
      <Box sx={{ display: 'flex', minHeight: '100dvh' }}>
        <SideMenu />
        <AppNavbar />
        {/*
          main — flex-колонка на всю высоту экрана: контент растягивается (flexGrow),
          поэтому копирайт прижат к нижней кромке, а не висит под графиком.
        */}
        <Box
          component="main"
          sx={(theme) => ({
            flexGrow: 1,
            minWidth: 0,
            minHeight: '100dvh',
            display: 'flex',
            flexDirection: 'column',
            backgroundColor: theme.vars
              ? `rgba(${theme.vars.palette.background.defaultChannel} / 1)`
              : alpha(theme.palette.background.default, 1),
            overflow: 'auto',
          })}
        >
          <Stack
            spacing={2}
            sx={{
              alignItems: 'center',
              mx: 3,
              pb: 2,
              mt: { xs: 8, md: 0 },
              flexGrow: 1,
            }}
          >
            <Header />
            <MainGrid />
          </Stack>
          <Copyright sx={{ py: 2 }} />
        </Box>
      </Box>
    </AppTheme>
  );
}
