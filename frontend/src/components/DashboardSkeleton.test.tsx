import React from 'react';
import { render, screen } from '@testing-library/react';
import { ThemeProvider, createTheme } from '@mui/material';
import {
  MetricCardSkeleton,
  ChartCardSkeleton,
  StatusBannerSkeleton,
  LiveDashboardSkeleton,
  PerformanceDashboardSkeleton,
} from './DashboardSkeleton';

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

describe('DashboardSkeleton', () => {
  describe('MetricCardSkeleton', () => {
    it('renders without crashing', () => {
      const { container } = renderWithTheme(<MetricCardSkeleton />);
      expect(container.firstChild).toBeInTheDocument();
    });

    it('renders a card element', () => {
      const { container } = renderWithTheme(<MetricCardSkeleton />);
      expect(container.querySelector('.MuiCard-root')).toBeInTheDocument();
    });

    it('renders multiple skeleton elements', () => {
      const { container } = renderWithTheme(<MetricCardSkeleton />);
      const skeletons = container.querySelectorAll('.MuiSkeleton-root');
      expect(skeletons.length).toBe(3); // text, text, circular
    });

    it('renders skeleton variants correctly', () => {
      const { container } = renderWithTheme(<MetricCardSkeleton />);
      expect(container.querySelector('.MuiSkeleton-text')).toBeInTheDocument();
      expect(container.querySelector('.MuiSkeleton-circular')).toBeInTheDocument();
    });
  });

  describe('ChartCardSkeleton', () => {
    it('renders without crashing', () => {
      const { container } = renderWithTheme(<ChartCardSkeleton />);
      expect(container.firstChild).toBeInTheDocument();
    });

    it('renders a card element', () => {
      const { container } = renderWithTheme(<ChartCardSkeleton />);
      expect(container.querySelector('.MuiCard-root')).toBeInTheDocument();
    });

    it('renders skeleton elements', () => {
      const { container } = renderWithTheme(<ChartCardSkeleton />);
      const skeletons = container.querySelectorAll('.MuiSkeleton-root');
      expect(skeletons.length).toBe(2); // text and rectangular
    });

    it('renders rectangular skeleton for chart area', () => {
      const { container } = renderWithTheme(<ChartCardSkeleton />);
      expect(container.querySelector('.MuiSkeleton-rectangular')).toBeInTheDocument();
    });

    it('uses default height of 300', () => {
      const { container } = renderWithTheme(<ChartCardSkeleton />);
      const rectSkeleton = container.querySelector('.MuiSkeleton-rectangular');
      expect(rectSkeleton).toHaveStyle({ height: '300px' });
    });

    it('uses custom height when provided', () => {
      const { container } = renderWithTheme(<ChartCardSkeleton height={400} />);
      const rectSkeleton = container.querySelector('.MuiSkeleton-rectangular');
      expect(rectSkeleton).toHaveStyle({ height: '400px' });
    });
  });

  describe('StatusBannerSkeleton', () => {
    it('renders without crashing', () => {
      const { container } = renderWithTheme(<StatusBannerSkeleton />);
      expect(container.firstChild).toBeInTheDocument();
    });

    it('renders a card element', () => {
      const { container } = renderWithTheme(<StatusBannerSkeleton />);
      expect(container.querySelector('.MuiCard-root')).toBeInTheDocument();
    });

    it('renders multiple skeleton elements', () => {
      const { container } = renderWithTheme(<StatusBannerSkeleton />);
      const skeletons = container.querySelectorAll('.MuiSkeleton-root');
      expect(skeletons.length).toBeGreaterThan(5);
    });

    it('renders rounded skeleton buttons', () => {
      const { container } = renderWithTheme(<StatusBannerSkeleton />);
      expect(container.querySelector('.MuiSkeleton-rounded')).toBeInTheDocument();
    });
  });

  describe('LiveDashboardSkeleton', () => {
    it('renders without crashing', () => {
      const { container } = renderWithTheme(<LiveDashboardSkeleton />);
      expect(container.firstChild).toBeInTheDocument();
    });

    it('renders grid container', () => {
      const { container } = renderWithTheme(<LiveDashboardSkeleton />);
      // MUI Grid container class
      const grid = container.querySelector('[class*="MuiGrid"]');
      expect(grid).toBeInTheDocument();
    });

    it('renders status banner skeletons', () => {
      const { container } = renderWithTheme(<LiveDashboardSkeleton />);
      // Should have 2 status banners + 4 metric cards + 2 cards = many card elements
      const cards = container.querySelectorAll('.MuiCard-root');
      expect(cards.length).toBeGreaterThan(6);
    });

    it('renders 4 metric card skeletons', () => {
      const { container } = renderWithTheme(<LiveDashboardSkeleton />);
      // Count circular skeletons which are unique to MetricCardSkeleton
      const circularSkeletons = container.querySelectorAll('.MuiSkeleton-circular');
      expect(circularSkeletons.length).toBe(4);
    });

    it('renders capital allocation and queue status sections', () => {
      const { container } = renderWithTheme(<LiveDashboardSkeleton />);
      const cards = container.querySelectorAll('.MuiCard-root');
      // 2 status banners + 4 metric cards + 2 bottom cards = 8 total
      expect(cards.length).toBe(8);
    });
  });

  describe('PerformanceDashboardSkeleton', () => {
    it('renders without crashing', () => {
      const { container } = renderWithTheme(<PerformanceDashboardSkeleton />);
      expect(container.firstChild).toBeInTheDocument();
    });

    it('renders grid container', () => {
      const { container } = renderWithTheme(<PerformanceDashboardSkeleton />);
      // MUI Grid container class
      const grid = container.querySelector('[class*="MuiGrid"]');
      expect(grid).toBeInTheDocument();
    });

    it('renders 4 metric card skeletons for PnL summary', () => {
      const { container } = renderWithTheme(<PerformanceDashboardSkeleton />);
      // MetricCardSkeleton has circular skeletons
      const circularSkeletons = container.querySelectorAll('.MuiSkeleton-circular');
      expect(circularSkeletons.length).toBe(4);
    });

    it('renders chart card skeletons', () => {
      const { container } = renderWithTheme(<PerformanceDashboardSkeleton />);
      // ChartCardSkeleton has rectangular skeletons
      const rectangularSkeletons = container.querySelectorAll('.MuiSkeleton-rectangular');
      expect(rectangularSkeletons.length).toBe(3); // 1 equity curve + 2 chart cards
    });

    it('renders multiple card elements', () => {
      const { container } = renderWithTheme(<PerformanceDashboardSkeleton />);
      const cards = container.querySelectorAll('.MuiCard-root');
      // 4 metric + 3 chart + 2 stats + 2 trades = 11 total
      expect(cards.length).toBe(11);
    });

    it('renders win/loss stats skeleton', () => {
      const { container } = renderWithTheme(<PerformanceDashboardSkeleton />);
      // Win/loss has 7 stat rows, risk has 5, trades have 5+5 = 22 total pairs
      const skeletons = container.querySelectorAll('.MuiSkeleton-text');
      expect(skeletons.length).toBeGreaterThan(20);
    });
  });
});
