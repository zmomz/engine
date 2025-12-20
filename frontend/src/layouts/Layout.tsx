import React from 'react';
import { Box, CssBaseline, ThemeProvider } from '@mui/material';
import { darkTheme } from '../theme/theme';

interface LayoutProps {
  children: React.ReactNode;
}

const Layout: React.FC<LayoutProps> = ({ children }) => {
  return (
    <ThemeProvider theme={darkTheme}>
      <CssBaseline />
      <Box sx={{ display: 'flex' }}>
        {children}
      </Box>
    </ThemeProvider>
  );
};

export default Layout;
