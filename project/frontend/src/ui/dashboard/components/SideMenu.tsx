import { useEffect, useState } from "react";
import { styled } from "@mui/material/styles";
import Avatar from "@mui/material/Avatar";
import MuiDrawer, { drawerClasses } from "@mui/material/Drawer";
import Box from "@mui/material/Box";
import Divider from "@mui/material/Divider";
import IconButton from "@mui/material/IconButton";
import Stack from "@mui/material/Stack";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import ChevronLeftRoundedIcon from "@mui/icons-material/ChevronLeftRounded";
import ChevronRightRoundedIcon from "@mui/icons-material/ChevronRightRounded";
import MenuContent from "./MenuContent";
import OptionsMenu from "./OptionsMenu";
import Logo from "../internals/components/Logo";

const drawerWidth = 240;
const collapsedWidth = 72;
const COLLAPSED_STORAGE_KEY = "investor.sidebarCollapsed";

function readCollapsed(): boolean {
  try {
    return localStorage.getItem(COLLAPSED_STORAGE_KEY) === "1";
  } catch {
    // localStorage недоступен (приватный режим, запрет cookies) — просто развёрнута
    return false;
  }
}

const Drawer = styled(MuiDrawer)({
  flexShrink: 0,
  boxSizing: "border-box",
  // mt: 10 из docs-шаблона убран: он добавлял 40px к высоте и вызывал скролл страницы.
  [`& .${drawerClasses.paper}`]: {
    boxSizing: "border-box",
    height: "100dvh",
    display: "flex",
    flexDirection: "column",
    overflow: "hidden",
    transition: "width 200ms ease",
  },
});

/** Маленькая кнопка-шеврон: 18px иконка в 22px кнопке. */
const toggleButtonSx = { p: 0.25, minWidth: 0 } as const;

export default function SideMenu() {
  const [collapsed, setCollapsed] = useState(readCollapsed);
  const width = collapsed ? collapsedWidth : drawerWidth;
  const toggle = () => setCollapsed((value) => !value);

  useEffect(() => {
    try {
      localStorage.setItem(COLLAPSED_STORAGE_KEY, collapsed ? "1" : "0");
    } catch {
      // сохранить состояние не удалось — не критично
    }
  }, [collapsed]);

  return (
    <Drawer
      variant="permanent"
      sx={{
        display: { xs: "none", md: "block" },
        width,
        transition: "width 200ms ease",
        [`& .${drawerClasses.paper}`]: {
          width,
          backgroundColor: "background.paper",
        },
      }}
    >
      {collapsed ? (
        <Stack sx={{ alignItems: "center", pt: 2, pb: 1.5, gap: 1.25 }}>
          <Logo size={26} />
          <Tooltip title="Развернуть" placement="right">
            <IconButton
              size="small"
              onClick={toggle}
              aria-label="Развернуть меню"
              sx={toggleButtonSx}
            >
              <ChevronRightRoundedIcon sx={{ fontSize: 18 }} />
            </IconButton>
          </Tooltip>
        </Stack>
      ) : (
        <Stack
          direction="row"
          sx={{ alignItems: "center", gap: 1, pl: 2.5, pr: 1.5, pt: 2.5, pb: 1.5 }}
        >
          <Logo size={26} />
          <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
            Investor
          </Typography>
          <Tooltip title="Свернуть">
            <IconButton
              size="small"
              onClick={toggle}
              aria-label="Свернуть меню"
              sx={{ ...toggleButtonSx, ml: "auto", mr: 0.5 }}
            >
              <ChevronLeftRoundedIcon sx={{ fontSize: 18 }} />
            </IconButton>
          </Tooltip>
        </Stack>
      )}

      <Divider />

      <Box
        sx={{
          display: "flex",
          justifyContent: collapsed ? "center" : "flex-start",
          p: collapsed ? 1.5 : 2,
        }}
      >
        <Stack direction="row" sx={{ gap: 1, alignItems: "center", minWidth: 0 }}>
          <Avatar
            sizes="small"
            alt="Иван Петров"
            src="/static/images/avatar/7.jpg"
            sx={{ width: 36, height: 36 }}
          />
          {!collapsed && (
            <>
              <Box sx={{ mr: "auto", minWidth: 0 }}>
                <Typography
                  variant="body2"
                  noWrap
                  sx={{ fontWeight: 500, lineHeight: "16px" }}
                >
                  Иван Петров
                </Typography>
                <Typography
                  variant="caption"
                  noWrap
                  sx={{ color: "text.secondary", display: "block" }}
                >
                  ivan@example.com
                </Typography>
              </Box>
              <OptionsMenu />
            </>
          )}
        </Stack>
      </Box>

      <Divider />

      <Box
        sx={{
          flexGrow: 1,
          minHeight: 0,
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
        }}
      >
        <MenuContent collapsed={collapsed} />
      </Box>
    </Drawer>
  );
}
