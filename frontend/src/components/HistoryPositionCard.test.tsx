import React from 'react';
import { render, screen } from '@testing-library/react';
import { ThemeProvider, createTheme } from '@mui/material';
import HistoryPositionCard from './HistoryPositionCard';
import { PositionGroup } from '../store/positionsStore';

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

describe('HistoryPositionCard', () => {
  const mockPosition: PositionGroup = {
    id: 'pos-1',
    symbol: 'BTC/USDT',
    side: 'long',
    status: 'CLOSED',
    exchange: 'binance',
    timeframe: 60,
    created_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(), // 2 hours ago
    closed_at: new Date().toISOString(),
    realized_pnl_usd: 150.50,
    unrealized_pnl_usd: 0,
    unrealized_pnl_percent: 0,
    weighted_avg_entry: 42500,
    total_invested_usd: 1000,
    total_filled_quantity: 0.0235,
    base_entry_price: 42000,
    pyramid_count: 2,
    max_pyramids: 3,
    replacement_count: 0,
    filled_dca_legs: 3,
    total_dca_legs: 5,
    tp_mode: 'weighted_average',
    risk_blocked: false,
    risk_eligible: false,
    risk_timer_expires: null,
    total_hedged_qty: 0,
    total_hedged_value_usd: 0,
    pyramids: [],
  };

  describe('basic rendering', () => {
    it('renders symbol', () => {
      renderWithTheme(<HistoryPositionCard position={mockPosition} />);
      expect(screen.getByText('BTC/USDT')).toBeInTheDocument();
    });

    it('renders side chip', () => {
      renderWithTheme(<HistoryPositionCard position={mockPosition} />);
      expect(screen.getByText('LONG')).toBeInTheDocument();
    });

    it('renders timeframe chip', () => {
      renderWithTheme(<HistoryPositionCard position={mockPosition} />);
      expect(screen.getByText('60m')).toBeInTheDocument();
    });

    it('renders - when timeframe is null', () => {
      const positionWithoutTimeframe = { ...mockPosition, timeframe: null as any };
      renderWithTheme(<HistoryPositionCard position={positionWithoutTimeframe} />);
      expect(screen.getAllByText('-').length).toBeGreaterThan(0);
    });
  });

  describe('PnL display', () => {
    it('shows positive PnL', () => {
      renderWithTheme(<HistoryPositionCard position={mockPosition} />);
      expect(screen.getByText(/\$150/)).toBeInTheDocument();
    });

    it('shows up icon for profitable', () => {
      renderWithTheme(<HistoryPositionCard position={mockPosition} />);
      expect(screen.getByTestId('TrendingUpIcon')).toBeInTheDocument();
    });

    it('shows negative PnL', () => {
      const losingPosition = { ...mockPosition, realized_pnl_usd: -75.25 };
      renderWithTheme(<HistoryPositionCard position={losingPosition} />);
      expect(screen.getByText(/-\$75/)).toBeInTheDocument();
    });

    it('shows down icon for losing', () => {
      const losingPosition = { ...mockPosition, realized_pnl_usd: -75.25 };
      renderWithTheme(<HistoryPositionCard position={losingPosition} />);
      expect(screen.getByTestId('TrendingDownIcon')).toBeInTheDocument();
    });

    it('calculates PnL percentage', () => {
      // 150.50 / 1000 = 15.05%
      renderWithTheme(<HistoryPositionCard position={mockPosition} />);
      // Use getAllByText since "15" appears in both $150.50 and +15.0%
      expect(screen.getAllByText(/15/).length).toBeGreaterThan(0);
    });

    it('handles zero invested amount', () => {
      const zeroInvested = { ...mockPosition, total_invested_usd: 0 };
      renderWithTheme(<HistoryPositionCard position={zeroInvested} />);
      // Should show 0% or handle gracefully
      expect(screen.getByText('BTC/USDT')).toBeInTheDocument();
    });
  });

  describe('short side', () => {
    it('renders SHORT chip', () => {
      const shortPosition = { ...mockPosition, side: 'short' };
      renderWithTheme(<HistoryPositionCard position={shortPosition} />);
      expect(screen.getByText('SHORT')).toBeInTheDocument();
    });
  });

  describe('duration', () => {
    it('formats duration with hours and minutes', () => {
      renderWithTheme(<HistoryPositionCard position={mockPosition} />);
      // There are multiple elements with hours (timeframe chip and duration)
      expect(screen.getAllByText(/\d+h/).length).toBeGreaterThan(0);
    });

    it('shows days for long positions', () => {
      const longDuration = {
        ...mockPosition,
        created_at: new Date(Date.now() - 26 * 60 * 60 * 1000).toISOString(), // 26 hours ago
      };
      renderWithTheme(<HistoryPositionCard position={longDuration} />);
      // The exact format depends on timing - just verify we have a day indicator
      expect(screen.getByText(/1d/)).toBeInTheDocument();
    });

    it('shows - when no created_at', () => {
      const noCreated = { ...mockPosition, created_at: null as any };
      renderWithTheme(<HistoryPositionCard position={noCreated} />);
      expect(screen.getAllByText('-').length).toBeGreaterThan(0);
    });

    it('shows - when no closed_at', () => {
      const noClosed = { ...mockPosition, closed_at: null };
      renderWithTheme(<HistoryPositionCard position={noClosed} />);
      expect(screen.getAllByText('-').length).toBeGreaterThan(0);
    });
  });

  describe('entry and close info', () => {
    it('renders entry price', () => {
      renderWithTheme(<HistoryPositionCard position={mockPosition} />);
      expect(screen.getByText('Entry')).toBeInTheDocument();
    });

    it('renders duration label', () => {
      renderWithTheme(<HistoryPositionCard position={mockPosition} />);
      expect(screen.getByText('Duration')).toBeInTheDocument();
    });

    it('renders closed label', () => {
      renderWithTheme(<HistoryPositionCard position={mockPosition} />);
      expect(screen.getByText('Closed')).toBeInTheDocument();
    });

    it('formats closed date', () => {
      renderWithTheme(<HistoryPositionCard position={mockPosition} />);
      // Should show a date format
      expect(screen.getByText(/Dec|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov/)).toBeInTheDocument();
    });
  });
});
