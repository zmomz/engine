import React from 'react';
import { render, screen } from '@testing-library/react';
import { ThemeProvider, createTheme } from '@mui/material';
import ActiveGroupsWidget from './ActiveGroupsWidget';

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

describe('ActiveGroupsWidget', () => {
  describe('rendering', () => {
    it('renders title', () => {
      renderWithTheme(<ActiveGroupsWidget count={5} />);
      expect(screen.getByText('Active Position Groups')).toBeInTheDocument();
    });

    it('renders count when provided', () => {
      renderWithTheme(<ActiveGroupsWidget count={10} />);
      expect(screen.getByText('10')).toBeInTheDocument();
    });

    it('renders zero count', () => {
      renderWithTheme(<ActiveGroupsWidget count={0} />);
      expect(screen.getByText('0')).toBeInTheDocument();
    });

    it('renders Loading... when count is null', () => {
      renderWithTheme(<ActiveGroupsWidget count={null} />);
      expect(screen.getByText('Loading...')).toBeInTheDocument();
    });
  });
});
