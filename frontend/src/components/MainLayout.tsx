import React from 'react';
import {
  AppBar,
  Toolbar,
  Typography,
  Drawer,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  IconButton,
  Box,
  CssBaseline,
} from '@mui/material';
import {
  Dashboard,
  ShowChart,
  PlaylistPlay,
  Security,
  Description,
  Settings,
  Brightness4,
  Brightness7,
  AccountCircle,
} from '@mui/icons-material';
import { NavLink } from 'react-router-dom';

const drawerWidth = 240;

interface MainLayoutProps {
  children: React.ReactNode;
}

const navItems = [
  { text: 'Dashboard', to: '/dashboard', icon: <Dashboard /> },
  { text: 'Positions', to: '/positions', icon: <ShowChart /> },
  { text: 'Queue', to: '/queue', icon: <PlaylistPlay /> },
  { text: 'Risk Engine', to: '/risk-engine', icon: <Security /> },
  { text: 'Logs', to: '/logs', icon: <Description /> },
  { text: 'Settings', to: '/settings', icon: <Settings /> },
];

const MainLayout: React.FC<MainLayoutProps> = ({ children }) => {
  return (
    <Box sx={{ display: 'flex' }}>
      <CssBaseline />
      <AppBar
        position="fixed"
        sx={{ zIndex: (theme) => theme.zIndex.drawer + 1 }}
      >
        <Toolbar>
          <Typography variant="h6" noWrap component="div" sx={{ flexGrow: 1 }} role="heading">
            Execution Engine
          </Typography>
          <IconButton sx={{ ml: 1 }} color="inherit" aria-label="Toggle theme">
            <Brightness7 />
          </IconButton>
          <IconButton
            size="large"
            edge="end"
            aria-label="user menu"
            aria-haspopup="true"
            color="inherit"
          >
            <AccountCircle />
          </IconButton>
        </Toolbar>
      </AppBar>
      <Drawer
        variant="permanent"
        sx={{
          width: drawerWidth,
          flexShrink: 0,
          [`& .MuiDrawer-paper`]: {
            width: drawerWidth,
            boxSizing: 'border-box',
          },
        }}
      >
        <Toolbar />
        <Box sx={{ overflow: 'auto' }}>
          <List>
            {navItems.map((item) => (
              <ListItem
                key={item.text}
                component={NavLink}
                to={item.to}
              >
                <ListItemIcon>{item.icon}</ListItemIcon>
                <ListItemText primary={item.text} />
              </ListItem>
            ))}
          </List>
        </Box>
      </Drawer>
      <Box
        component="main"
        sx={{ flexGrow: 1, bgcolor: 'background.default', p: 3 }}
      >
        <Toolbar />
        {children}
      </Box>
    </Box>
  );
};

export default MainLayout;