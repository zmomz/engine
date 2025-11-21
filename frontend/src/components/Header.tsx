import React from 'react';
import { AppBar, Toolbar, Typography, IconButton, Box } from '@mui/material';
import MenuIcon from '@mui/icons-material/Menu';

interface HeaderProps {
  onMenuClick: () => void;
}

const Header: React.FC<HeaderProps> = ({ onMenuClick }) => {
  return (
    <AppBar position="fixed" sx={{ zIndex: (theme) => theme.zIndex.drawer + 1 }}>
      <Toolbar>
        <IconButton
          color="inherit"
          aria-label="open drawer"
          edge="start"
          onClick={onMenuClick}
          sx={{ mr: 2, display: { sm: 'none' } }} // Hide on desktop, show on mobile
        >
          <MenuIcon />
        </IconButton>
        <Typography variant="h6" noWrap component="div">
          Trading Engine Dashboard
        </Typography>
        <Box sx={{ flexGrow: 1 }} />
        {/* Future: System Status Banner, Connection Health, User Profile */}
      </Toolbar>
    </AppBar>
  );
};

export default Header;
