import type { ReactNode } from 'react';
import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import ListItemButton from '@mui/material/ListItemButton';
import ListItemIcon from '@mui/material/ListItemIcon';
import ListItemText from '@mui/material/ListItemText';
import Stack from '@mui/material/Stack';
import Tooltip from '@mui/material/Tooltip';
import HomeRoundedIcon from '@mui/icons-material/HomeRounded';
import AnalyticsRoundedIcon from '@mui/icons-material/AnalyticsRounded';
import PeopleRoundedIcon from '@mui/icons-material/PeopleRounded';
import AssignmentRoundedIcon from '@mui/icons-material/AssignmentRounded';
import SettingsRoundedIcon from '@mui/icons-material/SettingsRounded';

type MenuEntry = {
  text: string;
  icon: ReactNode;
};

const mainListItems: MenuEntry[] = [
  { text: 'Главная', icon: <HomeRoundedIcon /> },
  { text: 'Аналитика', icon: <AnalyticsRoundedIcon /> },
  { text: 'Клиенты', icon: <PeopleRoundedIcon /> },
  { text: 'Задачи', icon: <AssignmentRoundedIcon /> },
];

const secondaryListItems: MenuEntry[] = [
  { text: 'Настройки', icon: <SettingsRoundedIcon /> },
];

type MenuItemRowProps = MenuEntry & {
  collapsed: boolean;
  selected?: boolean;
};

function MenuItemRow({ text, icon, collapsed, selected = false }: MenuItemRowProps) {
  const button = (
    <ListItemButton
      selected={selected}
      sx={collapsed ? { justifyContent: 'center', px: 1.5 } : undefined}
    >
      <ListItemIcon
        sx={
          collapsed
            ? {
                minWidth: 0,
                justifyContent: 'center',
                // Тема шаблона (MuiListItem) жёстко задаёт иконкам 1rem,
                // поэтому в свёрнутой панели переопределяем и размер бокса,
                // и font-size: 1.5rem = 24px.
                '& .MuiSvgIcon-root': {
                  width: '1.5rem',
                  height: '1.5rem',
                  fontSize: '1.5rem',
                },
              }
            : undefined
        }
      >
        {icon}
      </ListItemIcon>
      {!collapsed && <ListItemText primary={text} />}
    </ListItemButton>
  );

  return (
    <ListItem disablePadding sx={{ display: 'block' }}>
      {collapsed ? (
        <Tooltip title={text} placement="right">
          {button}
        </Tooltip>
      ) : (
        button
      )}
    </ListItem>
  );
}

type MenuContentProps = {
  /** Свёрнутая панель: остаются только иконки, подписи уходят в тултипы. */
  collapsed?: boolean;
};

export default function MenuContent({ collapsed = false }: MenuContentProps) {
  return (
    <Stack
      sx={{
        flexGrow: 1,
        p: collapsed ? 0.5 : 1,
        justifyContent: 'space-between',
      }}
    >
      <List dense>
        {mainListItems.map((item, index) => (
          <MenuItemRow
            key={item.text}
            {...item}
            collapsed={collapsed}
            selected={index === 0}
          />
        ))}
      </List>
      <List dense>
        {secondaryListItems.map((item) => (
          <MenuItemRow key={item.text} {...item} collapsed={collapsed} />
        ))}
      </List>
    </Stack>
  );
}
