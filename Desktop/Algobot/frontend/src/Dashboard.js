import React, { useState, createContext, useMemo } from 'react';
import { useAuth } from './App';
import BotControl from './BotControl';
import TradeHistory from './TradeHistory';
import Logs from './Logs';
import Chart from './Chart';
import {
  AppBar, Toolbar, Typography, IconButton, Drawer, List, ListItem, ListItemIcon, ListItemText,
  CssBaseline, Box, Switch, useTheme, ThemeProvider, createTheme
} from '@mui/material';
import MenuIcon from '@mui/icons-material/Menu';
import PowerSettingsNewIcon from '@mui/icons-material/PowerSettingsNew';
import HistoryIcon from '@mui/icons-material/History';
import ListAltIcon from '@mui/icons-material/ListAlt';
import ShowChartIcon from '@mui/icons-material/ShowChart';
import Brightness4Icon from '@mui/icons-material/Brightness4';
import Brightness7Icon from '@mui/icons-material/Brightness7';

const sections = [
  { key: 'bot', label: 'Bot Control', icon: <PowerSettingsNewIcon /> },
  { key: 'trades', label: 'Trade History', icon: <HistoryIcon /> },
  { key: 'logs', label: 'Logs', icon: <ListAltIcon /> },
  { key: 'chart', label: 'Chart', icon: <ShowChartIcon /> }
];

export const ColorModeContext = createContext({ toggleColorMode: () => {} });

export default function Dashboard() {
  const { logout } = useAuth();
  const [section, setSection] = useState('bot');
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [mode, setMode] = useState('light');

  const colorMode = useMemo(
    () => ({ toggleColorMode: () => setMode((prev) => (prev === 'light' ? 'dark' : 'light')) }),
    []
  );

  const theme = useMemo(
    () => createTheme({ palette: { mode } }),
    [mode]
  );

  return (
    <ColorModeContext.Provider value={colorMode}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <Box sx={{ display: 'flex' }}>
          <AppBar position="fixed" sx={{ zIndex: theme.zIndex.drawer + 1 }}>
            <Toolbar>
              <IconButton color="inherit" edge="start" onClick={() => setDrawerOpen(true)} sx={{ mr: 2 }}>
                <MenuIcon />
              </IconButton>
              <Typography variant="h6" sx={{ flexGrow: 1 }}>
                Dashboard
              </Typography>
              <IconButton color="inherit" onClick={colorMode.toggleColorMode}>
                {theme.palette.mode === 'dark' ? <Brightness7Icon /> : <Brightness4Icon />}
              </IconButton>
              <IconButton color="inherit" onClick={logout} sx={{ ml: 1 }}>
                <Typography variant="body2" sx={{ mr: 1 }}>Logout</Typography>
                <PowerSettingsNewIcon />
              </IconButton>
            </Toolbar>
          </AppBar>
          <Drawer
            variant="temporary"
            open={drawerOpen}
            onClose={() => setDrawerOpen(false)}
            sx={{
              width: 220,
              flexShrink: 0,
              '& .MuiDrawer-paper': { width: 220, boxSizing: 'border-box' },
            }}
          >
            <Toolbar />
            <List>
              {sections.map((s) => (
                <ListItem
                  button
                  key={s.key}
                  selected={section === s.key}
                  onClick={() => {
                    setSection(s.key);
                    setDrawerOpen(false);
                  }}
                >
                  <ListItemIcon>{s.icon}</ListItemIcon>
                  <ListItemText primary={s.label} />
                </ListItem>
              ))}
            </List>
          </Drawer>
          <Box
            component="main"
            sx={{ flexGrow: 1, p: 3, width: { sm: `calc(100% - 220px)` } }}
          >
            <Toolbar />
            {section === 'bot' && <BotControl />}
            {section === 'trades' && <TradeHistory />}
            {section === 'logs' && <Logs />}
            {section === 'chart' && <Chart />}
          </Box>
        </Box>
      </ThemeProvider>
    </ColorModeContext.Provider>
  );
} 