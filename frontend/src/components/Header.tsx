import React from 'react';
import { AppBar, Toolbar, Typography, IconButton, Box, Button, Tooltip } from '@mui/material';
import MenuIcon from '@mui/icons-material/Menu';
import Brightness4Icon from '@mui/icons-material/Brightness4';
import Brightness7Icon from '@mui/icons-material/Brightness7';
import useAuthStore from '../store/authStore';
import useThemeStore from '../store/themeStore';
import { useNavigate } from 'react-router-dom';

interface HeaderProps {
  onMenuClick: () => void;
}

const Header: React.FC<HeaderProps> = ({ onMenuClick }) => {
  const { isAuthenticated, logout } = useAuthStore();
  const { mode, toggleTheme } = useThemeStore();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <AppBar position="fixed" sx={{ zIndex: (theme) => theme.zIndex.drawer + 1 }}>
      <Toolbar>
        {isAuthenticated && (
          <IconButton
            color="inherit"
            aria-label="open drawer"
            edge="start"
            onClick={onMenuClick}
            sx={{ mr: 2, display: { sm: 'none' } }} // Hide on desktop, show on mobile
          >
            <MenuIcon />
          </IconButton>
        )}
        <Typography variant="h6" noWrap component="div">
          Trading Engine Dashboard
        </Typography>
        <Box sx={{ flexGrow: 1 }} />
        <Tooltip title={mode === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}>
          <IconButton
            color="inherit"
            onClick={toggleTheme}
            aria-label="toggle theme"
            sx={{ mr: 1 }}
          >
            {mode === 'dark' ? <Brightness7Icon /> : <Brightness4Icon />}
          </IconButton>
        </Tooltip>
        {isAuthenticated && (
          <Button color="inherit" onClick={handleLogout}>
            Sign Out
          </Button>
        )}
      </Toolbar>
    </AppBar>
  );
};

export default Header;
