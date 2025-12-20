import React, { useMemo } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  BottomNavigation,
  BottomNavigationAction,
  Paper,
  useTheme,
  useMediaQuery
} from '@mui/material';
import DashboardIcon from '@mui/icons-material/Dashboard';
import AccountBalanceWalletIcon from '@mui/icons-material/AccountBalanceWallet';
import SecurityIcon from '@mui/icons-material/Security';
import BarChartIcon from '@mui/icons-material/BarChart';
import SettingsIcon from '@mui/icons-material/Settings';
import QueueIcon from '@mui/icons-material/Queue';
import useAuthStore from '../store/authStore';

interface NavItem {
  label: string;
  icon: React.ReactNode;
  path: string;
}

const allNavItems: NavItem[] = [
  { label: 'Home', icon: <DashboardIcon />, path: '/dashboard' },
  { label: 'Positions', icon: <AccountBalanceWalletIcon />, path: '/positions' },
  { label: 'Queue', icon: <QueueIcon />, path: '/queue' },
  { label: 'Risk', icon: <SecurityIcon />, path: '/risk' },
  { label: 'Analytics', icon: <BarChartIcon />, path: '/analytics' },
  { label: 'Settings', icon: <SettingsIcon />, path: '/settings' },
];

const MobileBottomNav: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  const { isAuthenticated } = useAuthStore();

  // Filter out the current page from nav items
  const visibleNavItems = useMemo(() => {
    return allNavItems.filter(item => item.path !== location.pathname);
  }, [location.pathname]);

  // Don't show on desktop or when not authenticated
  if (!isMobile || !isAuthenticated) {
    return null;
  }

  // Don't show on login/register pages
  if (location.pathname === '/login' || location.pathname === '/register') {
    return null;
  }

  const handleChange = (_: React.SyntheticEvent, newValue: number) => {
    navigate(visibleNavItems[newValue].path);
  };

  return (
    <Paper
      sx={{
        position: 'fixed',
        bottom: 0,
        left: 0,
        right: 0,
        zIndex: theme.zIndex.appBar + 1,
        borderTop: '1px solid',
        borderColor: 'divider',
        pb: 'env(safe-area-inset-bottom)', // For iOS notch devices
      }}
      elevation={8}
    >
      <BottomNavigation
        value={false}
        onChange={handleChange}
        showLabels
        sx={{
          bgcolor: 'background.paper',
          height: 56,
          '& .MuiBottomNavigationAction-root': {
            minWidth: 'auto',
            padding: '4px 6px',
            color: 'text.secondary',
          },
          '& .MuiBottomNavigationAction-label': {
            fontSize: '0.6rem',
            marginTop: '2px',
          },
        }}
      >
        {visibleNavItems.map((item) => (
          <BottomNavigationAction
            key={item.path}
            label={item.label}
            icon={item.icon}
            sx={{
              '& .MuiSvgIcon-root': {
                fontSize: '1.3rem',
              },
            }}
          />
        ))}
      </BottomNavigation>
    </Paper>
  );
};

export default MobileBottomNav;
