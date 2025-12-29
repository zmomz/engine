import React from 'react';
import { render, screen } from '@testing-library/react';
import { ThemeProvider, createTheme } from '@mui/material';
import AppFooter from './AppFooter';

const theme = createTheme({
  palette: {
    mode: 'dark',
  },
});

const renderWithTheme = (component: React.ReactElement) => {
  return render(
    <ThemeProvider theme={theme}>
      {component}
    </ThemeProvider>
  );
};

describe('AppFooter', () => {
  describe('default (non-compact) mode', () => {
    it('renders version info', () => {
      renderWithTheme(<AppFooter />);
      expect(screen.getByText(/Trading Engine Dashboard v1\.0\.0/)).toBeInTheDocument();
    });

    it('renders build date chip', () => {
      renderWithTheme(<AppFooter />);
      expect(screen.getByText('Build 2025-12-18')).toBeInTheDocument();
    });

    it('renders Dark Mode chip', () => {
      renderWithTheme(<AppFooter />);
      expect(screen.getByText('Dark Mode')).toBeInTheDocument();
    });

    it('renders Real-time Updates chip', () => {
      renderWithTheme(<AppFooter />);
      expect(screen.getByText('Real-time Updates')).toBeInTheDocument();
    });

    it('renders info icon', () => {
      renderWithTheme(<AppFooter />);
      expect(screen.getByTestId('InfoIcon')).toBeInTheDocument();
    });
  });

  describe('compact mode', () => {
    it('renders compact version text', () => {
      renderWithTheme(<AppFooter compact={true} />);
      expect(screen.getByText(/Trading Engine v1\.0\.0/)).toBeInTheDocument();
    });

    it('does not render build date chip in compact mode', () => {
      renderWithTheme(<AppFooter compact={true} />);
      expect(screen.queryByText('Build 2025-12-18')).not.toBeInTheDocument();
    });

    it('does not render Dark Mode chip in compact mode', () => {
      renderWithTheme(<AppFooter compact={true} />);
      expect(screen.queryByText('Dark Mode')).not.toBeInTheDocument();
    });

    it('does not render info icon in compact mode', () => {
      renderWithTheme(<AppFooter compact={true} />);
      expect(screen.queryByTestId('InfoIcon')).not.toBeInTheDocument();
    });
  });

  describe('compact prop default', () => {
    it('defaults to non-compact mode', () => {
      renderWithTheme(<AppFooter />);
      // Full version is shown
      expect(screen.getByText(/Trading Engine Dashboard/)).toBeInTheDocument();
    });
  });
});
