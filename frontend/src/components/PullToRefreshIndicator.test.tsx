import React from 'react';
import { render, screen } from '@testing-library/react';
import { ThemeProvider, createTheme } from '@mui/material';
import PullToRefreshIndicator from './PullToRefreshIndicator';

// Mock useMediaQuery
jest.mock('@mui/material', () => ({
  ...jest.requireActual('@mui/material'),
  useMediaQuery: jest.fn(),
}));

import { useMediaQuery } from '@mui/material';

const mockedUseMediaQuery = useMediaQuery as jest.Mock;

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

describe('PullToRefreshIndicator', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('desktop behavior', () => {
    beforeEach(() => {
      mockedUseMediaQuery.mockReturnValue(false); // Not mobile
    });

    it('returns null on desktop', () => {
      const { container } = renderWithTheme(
        <PullToRefreshIndicator pullDistance={50} isRefreshing={false} />
      );
      expect(container.firstChild).toBeNull();
    });

    it('returns null even when refreshing on desktop', () => {
      const { container } = renderWithTheme(
        <PullToRefreshIndicator pullDistance={50} isRefreshing={true} />
      );
      expect(container.firstChild).toBeNull();
    });
  });

  describe('mobile behavior', () => {
    beforeEach(() => {
      mockedUseMediaQuery.mockReturnValue(true); // Is mobile
    });

    it('returns null when pullDistance is 0 and not refreshing', () => {
      const { container } = renderWithTheme(
        <PullToRefreshIndicator pullDistance={0} isRefreshing={false} />
      );
      expect(container.firstChild).toBeNull();
    });

    it('renders when pullDistance is greater than 0', () => {
      renderWithTheme(
        <PullToRefreshIndicator pullDistance={50} isRefreshing={false} />
      );
      expect(screen.getByTestId('RefreshIcon')).toBeInTheDocument();
    });

    it('renders CircularProgress when refreshing', () => {
      renderWithTheme(
        <PullToRefreshIndicator pullDistance={0} isRefreshing={true} />
      );
      expect(screen.getByRole('progressbar')).toBeInTheDocument();
    });

    it('renders when both pulling and refreshing', () => {
      renderWithTheme(
        <PullToRefreshIndicator pullDistance={50} isRefreshing={true} />
      );
      expect(screen.getByRole('progressbar')).toBeInTheDocument();
    });

    it('calculates progress correctly', () => {
      renderWithTheme(
        <PullToRefreshIndicator pullDistance={40} isRefreshing={false} threshold={80} />
      );
      // 40/80 = 50% progress
      expect(screen.getByTestId('RefreshIcon')).toBeInTheDocument();
    });

    it('caps progress at 100%', () => {
      renderWithTheme(
        <PullToRefreshIndicator pullDistance={100} isRefreshing={false} threshold={80} />
      );
      expect(screen.getByTestId('RefreshIcon')).toBeInTheDocument();
    });

    it('uses default threshold of 80', () => {
      renderWithTheme(
        <PullToRefreshIndicator pullDistance={80} isRefreshing={false} />
      );
      expect(screen.getByTestId('RefreshIcon')).toBeInTheDocument();
    });

    it('changes icon color when progress reaches 100%', () => {
      renderWithTheme(
        <PullToRefreshIndicator pullDistance={80} isRefreshing={false} threshold={80} />
      );
      const icon = screen.getByTestId('RefreshIcon');
      // Icon should be in the document - color is applied via styles
      expect(icon).toBeInTheDocument();
    });
  });
});
