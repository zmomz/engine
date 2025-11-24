import React from 'react';
import { AppBar, Toolbar, Typography, IconButton, Box, Button } from '@mui/material';
import MenuIcon from '@mui/icons-material/Menu';
import useAuthStore from '../store/authStore';
import { useNavigate } from 'react-router-dom';

interface HeaderProps {
  onMenuClick: () => void;
}

const Header: React.FC<HeaderProps> = ({ onMenuClick }) => {
  const { isAuthenticated, logout } = useAuthStore();
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
        {/* Future: System Status Banner, Connection Health, User Profile */}
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
