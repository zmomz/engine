import React from 'react';
import { Box, CssBaseline, ThemeProvider } from '@mui/material';
import { darkTheme, lightTheme } from '../theme/theme';
import useThemeStore from '../store/themeStore';

interface LayoutProps {
  children: React.ReactNode;
}

const Layout: React.FC<LayoutProps> = ({ children }) => {
  const mode = useThemeStore((state) => state.mode);
  const theme = mode === 'dark' ? darkTheme : lightTheme;

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Box sx={{ display: 'flex' }}>
        {children}
      </Box>
    </ThemeProvider>
  );
};

export default Layout;
