import { createTheme, ThemeOptions } from '@mui/material/styles';

// Extend the theme to include custom colors
declare module '@mui/material/styles' {
  interface Palette {
    bullish: Palette['primary'];
    bearish: Palette['primary'];
  }
  interface PaletteOptions {
    bullish?: PaletteOptions['primary'];
    bearish?: PaletteOptions['primary'];
  }
  interface TypographyVariants {
    fontFamilyMonospace: string;
  }
  interface TypographyVariantsOptions {
    fontFamilyMonospace?: string;
  }
}

// Define common typography and component settings
const commonSettings: ThemeOptions = {
  typography: {
    fontFamily: '"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    fontFamilyMonospace: '"JetBrains Mono", "Fira Code", "Consolas", monospace',
    // Display
    h1: { fontSize: '3rem', fontWeight: 700, lineHeight: 1.2 },
    h2: { fontSize: '2.25rem', fontWeight: 700, lineHeight: 1.3 },
    h3: { fontSize: '1.875rem', fontWeight: 600, lineHeight: 1.3 },
    h4: { fontSize: '1.5rem', fontWeight: 600, lineHeight: 1.4 },
    h5: { fontSize: '1.25rem', fontWeight: 600, lineHeight: 1.4 },
    h6: { fontSize: '1.125rem', fontWeight: 600, lineHeight: 1.4 },
    // Body
    body1: { fontSize: '1rem', lineHeight: 1.5 },
    body2: { fontSize: '0.875rem', lineHeight: 1.5 },
    caption: { fontSize: '0.75rem', lineHeight: 1.4 },
    button: { textTransform: 'none', fontWeight: 600 },
  },
  spacing: 8, // 8px base spacing
  shape: {
    borderRadius: 8,
  },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: 8,
          padding: '8px 16px',
          fontSize: '0.875rem',
          fontWeight: 600,
        },
        contained: {
          boxShadow: 'none',
          '&:hover': {
            boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.4)',
          },
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          borderRadius: 12,
          boxShadow: '0 1px 2px 0 rgba(0, 0, 0, 0.3)',
        },
      },
    },
    MuiAppBar: {
      styleOverrides: {
        root: {
          boxShadow: '0 1px 2px 0 rgba(0, 0, 0, 0.3)',
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: {
          fontWeight: 500,
        },
      },
    },
  },
};

// Light theme palette
const lightPalette = {
  primary: {
    main: '#6366f1',
    dark: '#4f46e5',
    light: '#818cf8',
  },
  secondary: {
    main: '#8b5cf6',
    dark: '#7c3aed',
    light: '#a78bfa',
  },
  background: {
    default: '#f4f6f8',
    paper: '#ffffff',
  },
  text: {
    primary: '#212121',
    secondary: '#757575',
  },
  bullish: {
    main: '#10b981',
    dark: '#047857',
    light: '#34d399',
    contrastText: '#ffffff',
  },
  bearish: {
    main: '#ef4444',
    dark: '#b91c1c',
    light: '#f87171',
    contrastText: '#ffffff',
  },
  success: {
    main: '#10b981',
  },
  warning: {
    main: '#f59e0b',
  },
  error: {
    main: '#ef4444',
  },
};

// Dark theme palette (Trading Terminal Style)
const darkPalette = {
  primary: {
    main: '#6366f1',
    dark: '#4f46e5',
    light: '#818cf8',
  },
  secondary: {
    main: '#8b5cf6',
    dark: '#7c3aed',
    light: '#a78bfa',
  },
  background: {
    default: '#0a0e1a',
    paper: '#131823',
  },
  text: {
    primary: '#e8eaed',
    secondary: '#9ca3af',
  },
  bullish: {
    main: '#10b981',
    dark: '#047857',
    light: '#34d399',
    contrastText: '#ffffff',
  },
  bearish: {
    main: '#ef4444',
    dark: '#b91c1c',
    light: '#f87171',
    contrastText: '#ffffff',
  },
  success: {
    main: '#10b981',
    dark: '#047857',
    light: '#34d399',
  },
  warning: {
    main: '#f59e0b',
    dark: '#d97706',
    light: '#fbbf24',
  },
  error: {
    main: '#ef4444',
    dark: '#b91c1c',
    light: '#f87171',
  },
  info: {
    main: '#3b82f6',
    dark: '#2563eb',
    light: '#60a5fa',
  },
  divider: 'rgba(255, 255, 255, 0.1)',
};

export const lightTheme = createTheme({
  palette: {
    mode: 'light',
    ...lightPalette,
  },
  ...commonSettings,
});

export const darkTheme = createTheme({
  palette: {
    mode: 'dark',
    ...darkPalette,
  },
  ...commonSettings,
});
