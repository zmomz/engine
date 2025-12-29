import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { ThemeProvider, createTheme } from '@mui/material';
import PositionCard from './PositionCard';
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

describe('PositionCard', () => {
  const mockOnForceClose = jest.fn();

  const mockPosition: PositionGroup = {
    id: 'pos-1',
    symbol: 'BTC/USDT',
    side: 'long',
    status: 'ACTIVE',
    exchange: 'binance',
    timeframe: 60,
    created_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(), // 2 hours ago
    closed_at: null,
    unrealized_pnl_usd: 150.50,
    unrealized_pnl_percent: 5.25,
    realized_pnl_usd: 0,
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
    risk_eligible: true,
    risk_timer_expires: null,
    total_hedged_qty: 0,
    total_hedged_value_usd: 0,
    pyramids: [],
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('basic rendering', () => {
    it('renders position symbol', () => {
      renderWithTheme(<PositionCard position={mockPosition} onForceClose={mockOnForceClose} />);
      expect(screen.getByText('BTC/USDT')).toBeInTheDocument();
    });

    it('renders side chip', () => {
      renderWithTheme(<PositionCard position={mockPosition} onForceClose={mockOnForceClose} />);
      expect(screen.getByText('LONG')).toBeInTheDocument();
    });

    it('renders status chip', () => {
      renderWithTheme(<PositionCard position={mockPosition} onForceClose={mockOnForceClose} />);
      expect(screen.getByText('ACTIVE')).toBeInTheDocument();
    });

    it('renders PnL', () => {
      renderWithTheme(<PositionCard position={mockPosition} onForceClose={mockOnForceClose} />);
      expect(screen.getByText('$150.50')).toBeInTheDocument();
      // formatCompactPercent rounds to 1 decimal place
      expect(screen.getByText('+5.3%')).toBeInTheDocument();
    });
  });

  describe('PnL display', () => {
    it('shows positive PnL with correct styling', () => {
      renderWithTheme(<PositionCard position={mockPosition} onForceClose={mockOnForceClose} />);
      expect(screen.getByTestId('TrendingUpIcon')).toBeInTheDocument();
    });

    it('shows negative PnL with correct styling', () => {
      const losingPosition = {
        ...mockPosition,
        unrealized_pnl_usd: -75.25,
        unrealized_pnl_percent: -3.5,
      };
      renderWithTheme(<PositionCard position={losingPosition} onForceClose={mockOnForceClose} />);
      expect(screen.getByTestId('TrendingDownIcon')).toBeInTheDocument();
      expect(screen.getByText('-$75.25')).toBeInTheDocument();
    });
  });

  describe('quick stats', () => {
    it('renders entry price', () => {
      renderWithTheme(<PositionCard position={mockPosition} onForceClose={mockOnForceClose} />);
      expect(screen.getByText('Entry')).toBeInTheDocument();
      // The exact format depends on locale settings, so just check it contains the value
      expect(screen.getByText(/42.*500/)).toBeInTheDocument();
    });

    it('renders invested amount', () => {
      renderWithTheme(<PositionCard position={mockPosition} onForceClose={mockOnForceClose} />);
      expect(screen.getByText('Invested')).toBeInTheDocument();
      // The exact format depends on locale, check it contains the value
      expect(screen.getByText(/1.*000/)).toBeInTheDocument();
    });

    it('renders age', () => {
      renderWithTheme(<PositionCard position={mockPosition} onForceClose={mockOnForceClose} />);
      expect(screen.getByText('Age')).toBeInTheDocument();
      expect(screen.getByText('2h')).toBeInTheDocument();
    });

    it('shows days for old positions', () => {
      const oldPosition = {
        ...mockPosition,
        created_at: new Date(Date.now() - 26 * 60 * 60 * 1000).toISOString(), // 26 hours ago
      };
      renderWithTheme(<PositionCard position={oldPosition} onForceClose={mockOnForceClose} />);
      expect(screen.getByText('1d 2h')).toBeInTheDocument();
    });

    it('handles missing created_at', () => {
      const noCreatedAt = { ...mockPosition, created_at: null as any };
      renderWithTheme(<PositionCard position={noCreatedAt} onForceClose={mockOnForceClose} />);
      expect(screen.getByText('-')).toBeInTheDocument();
    });
  });

  describe('progress bars', () => {
    it('renders pyramid progress', () => {
      renderWithTheme(<PositionCard position={mockPosition} onForceClose={mockOnForceClose} />);
      expect(screen.getByText('Pyramids: 2/3')).toBeInTheDocument();
    });

    it('renders DCA progress', () => {
      renderWithTheme(<PositionCard position={mockPosition} onForceClose={mockOnForceClose} />);
      expect(screen.getByText('DCA: 3/5')).toBeInTheDocument();
    });

    it('handles zero max pyramids', () => {
      const noPyramids = { ...mockPosition, max_pyramids: 0, pyramid_count: 0 };
      renderWithTheme(<PositionCard position={noPyramids} onForceClose={mockOnForceClose} />);
      expect(screen.getByText('Pyramids: 0/0')).toBeInTheDocument();
    });

    it('handles zero total DCA legs', () => {
      const noDca = { ...mockPosition, total_dca_legs: 0, filled_dca_legs: 0 };
      renderWithTheme(<PositionCard position={noDca} onForceClose={mockOnForceClose} />);
      expect(screen.getByText('DCA: 0/0')).toBeInTheDocument();
    });
  });

  describe('Force Close button', () => {
    it('calls onForceClose when clicked', () => {
      renderWithTheme(<PositionCard position={mockPosition} onForceClose={mockOnForceClose} />);
      fireEvent.click(screen.getByText('Force Close'));
      expect(mockOnForceClose).toHaveBeenCalledWith('pos-1');
    });

    it('is disabled when status is CLOSING', () => {
      const closingPosition = { ...mockPosition, status: 'CLOSING' };
      renderWithTheme(<PositionCard position={closingPosition} onForceClose={mockOnForceClose} />);
      expect(screen.getByText('Force Close')).toBeDisabled();
    });

    it('is disabled when status is CLOSED', () => {
      const closedPosition = { ...mockPosition, status: 'CLOSED' };
      renderWithTheme(<PositionCard position={closedPosition} onForceClose={mockOnForceClose} />);
      expect(screen.getByText('Force Close')).toBeDisabled();
    });
  });

  describe('expand/collapse', () => {
    it('expands when expand button clicked', () => {
      renderWithTheme(<PositionCard position={mockPosition} onForceClose={mockOnForceClose} />);

      // Click expand
      fireEvent.click(screen.getByTestId('KeyboardArrowDownIcon'));

      // Now visible
      expect(screen.getByText('Base Entry')).toBeInTheDocument();
    });

    it('collapses when collapse button clicked', async () => {
      renderWithTheme(<PositionCard position={mockPosition} onForceClose={mockOnForceClose} />);

      // Expand
      fireEvent.click(screen.getByTestId('KeyboardArrowDownIcon'));
      expect(screen.getByText('Base Entry')).toBeInTheDocument();

      // Collapse - just verify the button toggles
      fireEvent.click(screen.getByTestId('KeyboardArrowUpIcon'));
      // After collapse, the down icon should be visible again
      expect(screen.getByTestId('KeyboardArrowDownIcon')).toBeInTheDocument();
    });
  });

  describe('expanded details', () => {
    it('shows TP mode', () => {
      renderWithTheme(<PositionCard position={mockPosition} onForceClose={mockOnForceClose} />);
      fireEvent.click(screen.getByTestId('KeyboardArrowDownIcon'));

      expect(screen.getByText('TP Mode')).toBeInTheDocument();
      expect(screen.getByText('WEIGHTED AVERAGE')).toBeInTheDocument();
    });

    it('shows total quantity', () => {
      renderWithTheme(<PositionCard position={mockPosition} onForceClose={mockOnForceClose} />);
      fireEvent.click(screen.getByTestId('KeyboardArrowDownIcon'));

      expect(screen.getByText('Total Quantity')).toBeInTheDocument();
      expect(screen.getByText('0.0235')).toBeInTheDocument();
    });

    it('shows risk status - eligible', () => {
      renderWithTheme(<PositionCard position={mockPosition} onForceClose={mockOnForceClose} />);
      fireEvent.click(screen.getByTestId('KeyboardArrowDownIcon'));

      expect(screen.getByText('Risk Status')).toBeInTheDocument();
      expect(screen.getByText('✅ Eligible')).toBeInTheDocument();
    });

    it('shows risk status - blocked', () => {
      const blockedPosition = { ...mockPosition, risk_blocked: true, risk_eligible: false };
      renderWithTheme(<PositionCard position={blockedPosition} onForceClose={mockOnForceClose} />);
      fireEvent.click(screen.getByTestId('KeyboardArrowDownIcon'));

      expect(screen.getByText('⚠️ Blocked')).toBeInTheDocument();
    });

    it('shows risk status - N/A', () => {
      const naPosition = { ...mockPosition, risk_blocked: false, risk_eligible: false };
      renderWithTheme(<PositionCard position={naPosition} onForceClose={mockOnForceClose} />);
      fireEvent.click(screen.getByTestId('KeyboardArrowDownIcon'));

      expect(screen.getByText('○ N/A')).toBeInTheDocument();
    });

    it('shows hedged info when available', () => {
      const hedgedPosition = {
        ...mockPosition,
        total_hedged_qty: 0.005,
        total_hedged_value_usd: 212.50,
      };
      renderWithTheme(<PositionCard position={hedgedPosition} onForceClose={mockOnForceClose} />);
      fireEvent.click(screen.getByTestId('KeyboardArrowDownIcon'));

      expect(screen.getByText('Hedged Qty ℹ️')).toBeInTheDocument();
      expect(screen.getByText('0.0050')).toBeInTheDocument();
      expect(screen.getByText('Hedged Value ℹ️')).toBeInTheDocument();
      expect(screen.getByText('$212.50')).toBeInTheDocument();
    });

    it('hides hedged info when zero', () => {
      renderWithTheme(<PositionCard position={mockPosition} onForceClose={mockOnForceClose} />);
      fireEvent.click(screen.getByTestId('KeyboardArrowDownIcon'));

      expect(screen.queryByText('Hedged Qty ℹ️')).not.toBeInTheDocument();
    });

    it('shows risk timer when set', () => {
      const timerPosition = {
        ...mockPosition,
        risk_timer_expires: new Date(Date.now() + 5 * 60 * 1000).toISOString(),
      };
      renderWithTheme(<PositionCard position={timerPosition} onForceClose={mockOnForceClose} />);
      fireEvent.click(screen.getByTestId('KeyboardArrowDownIcon'));

      expect(screen.getByText(/Risk Timer/)).toBeInTheDocument();
    });
  });

  describe('short side', () => {
    it('renders SHORT chip for short side', () => {
      const shortPosition = { ...mockPosition, side: 'short' };
      renderWithTheme(<PositionCard position={shortPosition} onForceClose={mockOnForceClose} />);
      expect(screen.getByText('SHORT')).toBeInTheDocument();
    });
  });

  describe('edge cases', () => {
    it('handles null tp_mode', () => {
      const noTpMode = { ...mockPosition, tp_mode: null as any };
      renderWithTheme(<PositionCard position={noTpMode} onForceClose={mockOnForceClose} />);
      fireEvent.click(screen.getByTestId('KeyboardArrowDownIcon'));

      expect(screen.getByText('-')).toBeInTheDocument();
    });

    it('handles null total_filled_quantity', () => {
      const noQuantity = { ...mockPosition, total_filled_quantity: null as any };
      renderWithTheme(<PositionCard position={noQuantity} onForceClose={mockOnForceClose} />);
      fireEvent.click(screen.getByTestId('KeyboardArrowDownIcon'));

      expect(screen.getAllByText('-').length).toBeGreaterThan(0);
    });

    it('handles null filled_dca_legs', () => {
      const noFilledDca = { ...mockPosition, filled_dca_legs: null as any };
      renderWithTheme(<PositionCard position={noFilledDca} onForceClose={mockOnForceClose} />);
      expect(screen.getByText('DCA: 0/5')).toBeInTheDocument();
    });
  });
});
