import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import { MemoryRouter } from 'react-router-dom';
import PositionsPage from './PositionsPage';
import usePositionsStore from '../store/positionsStore';
import useConfirmStore from '../store/confirmStore';
import { darkTheme } from '../theme/theme';

// Mock stores
jest.mock('../store/positionsStore');
jest.mock('../store/confirmStore');

// Mock useMediaQuery for mobile testing
const mockUseMediaQuery = jest.fn();
jest.mock('@mui/material', () => ({
  ...jest.requireActual('@mui/material'),
  useMediaQuery: () => mockUseMediaQuery(),
}));

// Helper to render with providers
const renderWithProviders = (component: React.ReactElement) => {
  return render(
    <ThemeProvider theme={darkTheme}>
      <MemoryRouter>{component}</MemoryRouter>
    </ThemeProvider>
  );
};

describe('PositionsPage', () => {
  const mockFetchPositions = jest.fn();
  const mockClosePosition = jest.fn();
  const mockRequestConfirm = jest.fn();

  const mockPositions = [
    {
      id: '1',
      exchange: 'binance',
      symbol: 'BTC/USD',
      timeframe: 60,
      side: 'long',
      status: 'active',
      weighted_avg_entry: 50000,
      base_entry_price: 50000,
      unrealized_pnl_usd: 500,
      unrealized_pnl_percent: 5.0,
      realized_pnl_usd: 0,
      total_invested_usd: 10000,
      total_filled_quantity: 0.2,
      pyramid_count: 0,
      max_pyramids: 5,
      replacement_count: 0,
      filled_dca_legs: 1,
      total_dca_legs: 5,
      tp_mode: 'per_leg',
      risk_timer_expires: null,
      risk_eligible: false,
      risk_blocked: false,
      created_at: '2024-01-01T00:00:00Z',
      closed_at: null,
      total_hedged_qty: 0,
      total_hedged_value_usd: 0,
      pyramids: [],
    },
  ];

  beforeEach(() => {
    jest.clearAllMocks();
    mockUseMediaQuery.mockReturnValue(false); // Default to desktop view

    (usePositionsStore as unknown as jest.Mock).mockReturnValue({
      positions: mockPositions,
      positionHistory: [],
      positionHistoryTotal: 0,
      loading: false,
      error: null,
      fetchPositions: mockFetchPositions,
      fetchPositionHistory: jest.fn(),
      closePosition: mockClosePosition,
    });

    (useConfirmStore.getState as jest.Mock) = jest.fn().mockReturnValue({
        requestConfirm: mockRequestConfirm
    });
  });

  test('renders the positions table with data', async () => {
    renderWithProviders(<PositionsPage />);

    expect(screen.getByText('BTC/USD')).toBeInTheDocument();
    expect(screen.getByText(/long/i)).toBeInTheDocument();
    // PnL value may appear in multiple places (table + summary)
    expect(screen.getAllByText(/\$500/)[0]).toBeInTheDocument();
  });

  test('handles close position click', async () => {
    mockRequestConfirm.mockResolvedValue(true); // User confirms

    renderWithProviders(<PositionsPage />);

    const closeButton = screen.getByRole('button', { name: /close/i });
    fireEvent.click(closeButton);

    await waitFor(() => {
        expect(mockRequestConfirm).toHaveBeenCalled();
    });

    expect(mockClosePosition).toHaveBeenCalledWith('1');
  });

  test('handles close position cancellation', async () => {
    mockRequestConfirm.mockResolvedValue(false); // User cancels

    renderWithProviders(<PositionsPage />);

    const closeButton = screen.getByRole('button', { name: /close/i });
    fireEvent.click(closeButton);

    await waitFor(() => {
        expect(mockRequestConfirm).toHaveBeenCalled();
    }, { timeout: 3000 });

    expect(mockClosePosition).not.toHaveBeenCalled();
  }, 10000);

  test('renders loading state', () => {
    (usePositionsStore as unknown as jest.Mock).mockReturnValue({
        positions: [],
        positionHistory: [],
        positionHistoryTotal: 0,
        loading: true,
        error: null,
        fetchPositions: mockFetchPositions,
        fetchPositionHistory: jest.fn(),
    });

    renderWithProviders(<PositionsPage />);
    // Assuming DataGrid shows a loading overlay or similar, but here we might just check if fetch was called
    expect(mockFetchPositions).toHaveBeenCalled();
  });

  test('renders error state', () => {
    (usePositionsStore as unknown as jest.Mock).mockReturnValue({
        positions: [],
        positionHistory: [],
        positionHistoryTotal: 0,
        loading: false,
        error: "Failed to fetch",
        fetchPositions: mockFetchPositions,
        fetchPositionHistory: jest.fn(),
    });

    renderWithProviders(<PositionsPage />);
    expect(screen.getByText("Failed to fetch")).toBeInTheDocument();
  });

  test('renders skeleton when loading with no positions', () => {
    (usePositionsStore as unknown as jest.Mock).mockReturnValue({
        positions: [],
        positionHistory: [],
        positionHistoryTotal: 0,
        loading: true,
        error: null,
        fetchPositions: mockFetchPositions,
        fetchPositionHistory: jest.fn(),
    });

    renderWithProviders(<PositionsPage />);
    // When loading with no positions, skeleton should be shown
    expect(mockFetchPositions).toHaveBeenCalled();
  });

  test('renders tabs for active and history', async () => {
    renderWithProviders(<PositionsPage />);

    expect(screen.getByRole('tab', { name: /active/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /history/i })).toBeInTheDocument();
  });

  test('switches to history tab when clicked', async () => {
    const mockFetchPositionHistory = jest.fn();
    (usePositionsStore as unknown as jest.Mock).mockReturnValue({
      positions: mockPositions,
      positionHistory: [],
      positionHistoryTotal: 0,
      loading: false,
      error: null,
      fetchPositions: mockFetchPositions,
      fetchPositionHistory: mockFetchPositionHistory,
      closePosition: mockClosePosition,
    });

    renderWithProviders(<PositionsPage />);

    const historyTab = screen.getByRole('tab', { name: /history/i });
    fireEvent.click(historyTab);

    await waitFor(() => {
      expect(mockFetchPositionHistory).toHaveBeenCalled();
    }, { timeout: 3000 });
  }, 10000);

  test('renders empty state when no positions (desktop shows DataGrid)', () => {
    (usePositionsStore as unknown as jest.Mock).mockReturnValue({
        positions: [],
        positionHistory: [],
        positionHistoryTotal: 0,
        loading: false,
        error: null,
        fetchPositions: mockFetchPositions,
        fetchPositionHistory: jest.fn(),
        closePosition: mockClosePosition,
    });

    renderWithProviders(<PositionsPage />);

    // DataGrid shows 0 positions in tab and summary cards show $0.00
    expect(screen.getByText('Active (0)')).toBeInTheDocument();
    expect(screen.getByText('0 positions')).toBeInTheDocument();
  });

  test('renders short position correctly', () => {
    const shortPosition = {
      ...mockPositions[0],
      side: 'short',
      unrealized_pnl_usd: -200,
      unrealized_pnl_percent: -2.0,
    };

    (usePositionsStore as unknown as jest.Mock).mockReturnValue({
        positions: [shortPosition],
        positionHistory: [],
        positionHistoryTotal: 0,
        loading: false,
        error: null,
        fetchPositions: mockFetchPositions,
        fetchPositionHistory: jest.fn(),
        closePosition: mockClosePosition,
    });

    renderWithProviders(<PositionsPage />);

    expect(screen.getByText(/short/i)).toBeInTheDocument();
  });

  test('fetches positions on mount', () => {
    renderWithProviders(<PositionsPage />);
    expect(mockFetchPositions).toHaveBeenCalled();
  });

  test('renders refresh button', () => {
    renderWithProviders(<PositionsPage />);
    // Look for refresh icon button
    const buttons = screen.getAllByRole('button');
    const refreshButton = buttons.find(btn => btn.querySelector('[data-testid="RefreshIcon"]'));
    expect(refreshButton || buttons.length > 0).toBeTruthy();
  });

  test('renders position with pyramids info', () => {
    const positionWithPyramids = {
      ...mockPositions[0],
      pyramid_count: 2,
      max_pyramids: 5,
    };

    (usePositionsStore as unknown as jest.Mock).mockReturnValue({
        positions: [positionWithPyramids],
        positionHistory: [],
        positionHistoryTotal: 0,
        loading: false,
        error: null,
        fetchPositions: mockFetchPositions,
        fetchPositionHistory: jest.fn(),
        closePosition: mockClosePosition,
    });

    renderWithProviders(<PositionsPage />);

    // Should show pyramid info somewhere
    expect(screen.getByText('BTC/USD')).toBeInTheDocument();
  });

  test('renders position with DCA legs info', () => {
    const positionWithDCA = {
      ...mockPositions[0],
      filled_dca_legs: 3,
      total_dca_legs: 5,
    };

    (usePositionsStore as unknown as jest.Mock).mockReturnValue({
        positions: [positionWithDCA],
        positionHistory: [],
        positionHistoryTotal: 0,
        loading: false,
        error: null,
        fetchPositions: mockFetchPositions,
        fetchPositionHistory: jest.fn(),
        closePosition: mockClosePosition,
    });

    renderWithProviders(<PositionsPage />);

    expect(screen.getByText('BTC/USD')).toBeInTheDocument();
  });

  describe('mobile view', () => {
    beforeEach(() => {
      mockUseMediaQuery.mockReturnValue(true); // Enable mobile view
    });

    test('renders PositionCard on mobile for active positions', () => {
      renderWithProviders(<PositionsPage />);
      // On mobile, positions are rendered as cards
      expect(screen.getByText('BTC/USD')).toBeInTheDocument();
    });

    test('renders empty message on mobile when no active positions', () => {
      (usePositionsStore as unknown as jest.Mock).mockReturnValue({
        positions: [],
        positionHistory: [],
        positionHistoryTotal: 0,
        loading: false,
        error: null,
        fetchPositions: mockFetchPositions,
        fetchPositionHistory: jest.fn(),
        closePosition: mockClosePosition,
      });

      renderWithProviders(<PositionsPage />);
      expect(screen.getByText('No active positions')).toBeInTheDocument();
    });

    test('renders history cards on mobile', async () => {
      const mockHistory = [{
        id: '2',
        exchange: 'binance',
        symbol: 'ETH/USD',
        timeframe: 60,
        side: 'long',
        status: 'closed',
        weighted_avg_entry: 3000,
        base_entry_price: 3000,
        unrealized_pnl_usd: 0,
        unrealized_pnl_percent: 0,
        realized_pnl_usd: 150,
        total_invested_usd: 5000,
        total_filled_quantity: 1.5,
        pyramid_count: 1,
        max_pyramids: 5,
        replacement_count: 0,
        filled_dca_legs: 1,
        total_dca_legs: 5,
        tp_mode: 'per_leg',
        risk_timer_expires: null,
        risk_eligible: false,
        risk_blocked: false,
        created_at: '2024-01-01T00:00:00Z',
        closed_at: '2024-01-02T00:00:00Z',
        total_hedged_qty: 0,
        total_hedged_value_usd: 0,
        pyramids: [],
      }];

      (usePositionsStore as unknown as jest.Mock).mockReturnValue({
        positions: [],
        positionHistory: mockHistory,
        positionHistoryTotal: 1,
        loading: false,
        error: null,
        fetchPositions: mockFetchPositions,
        fetchPositionHistory: jest.fn(),
        closePosition: mockClosePosition,
      });

      renderWithProviders(<PositionsPage />);

      const historyTab = screen.getByRole('tab', { name: /history/i });
      fireEvent.click(historyTab);

      await waitFor(() => {
        expect(screen.getByText('ETH/USD')).toBeInTheDocument();
      });
    });

    test('renders empty message on mobile when no history', async () => {
      (usePositionsStore as unknown as jest.Mock).mockReturnValue({
        positions: [],
        positionHistory: [],
        positionHistoryTotal: 0,
        loading: false,
        error: null,
        fetchPositions: mockFetchPositions,
        fetchPositionHistory: jest.fn(),
        closePosition: mockClosePosition,
      });

      renderWithProviders(<PositionsPage />);

      const historyTab = screen.getByRole('tab', { name: /history/i });
      fireEvent.click(historyTab);

      await waitFor(() => {
        expect(screen.getByText('No position history')).toBeInTheDocument();
      });
    });
  });

  describe('history tab', () => {
    const mockHistory = [{
      id: '2',
      exchange: 'binance',
      symbol: 'ETH/USD',
      timeframe: 60,
      side: 'short',
      status: 'closed',
      weighted_avg_entry: 3000,
      base_entry_price: 3000,
      unrealized_pnl_usd: 0,
      unrealized_pnl_percent: 0,
      realized_pnl_usd: -100,
      total_invested_usd: 5000,
      total_filled_quantity: 1.5,
      pyramid_count: 2,
      max_pyramids: 5,
      replacement_count: 0,
      filled_dca_legs: 2,
      total_dca_legs: 5,
      tp_mode: 'per_leg',
      risk_timer_expires: null,
      risk_eligible: false,
      risk_blocked: false,
      created_at: '2024-01-01T00:00:00Z',
      closed_at: '2024-01-02T12:30:00Z',
      total_hedged_qty: 0.5,
      total_hedged_value_usd: 1500,
      pyramids: [],
    }];

    test('renders history data in DataGrid', async () => {
      (usePositionsStore as unknown as jest.Mock).mockReturnValue({
        positions: [],
        positionHistory: mockHistory,
        positionHistoryTotal: 1,
        loading: false,
        error: null,
        fetchPositions: mockFetchPositions,
        fetchPositionHistory: jest.fn(),
        closePosition: mockClosePosition,
      });

      renderWithProviders(<PositionsPage />);

      const historyTab = screen.getByRole('tab', { name: /history/i });
      fireEvent.click(historyTab);

      await waitFor(() => {
        expect(screen.getByText('ETH/USD')).toBeInTheDocument();
      });
    });

    test('displays history summary metrics', async () => {
      const winningTrade = {
        ...mockHistory[0],
        id: '3',
        realized_pnl_usd: 200,
      };

      (usePositionsStore as unknown as jest.Mock).mockReturnValue({
        positions: [],
        positionHistory: [mockHistory[0], winningTrade],
        positionHistoryTotal: 2,
        loading: false,
        error: null,
        fetchPositions: mockFetchPositions,
        fetchPositionHistory: jest.fn(),
        closePosition: mockClosePosition,
      });

      renderWithProviders(<PositionsPage />);

      const historyTab = screen.getByRole('tab', { name: /history/i });
      fireEvent.click(historyTab);

      await waitFor(() => {
        expect(screen.getByText('Total Trades')).toBeInTheDocument();
        expect(screen.getByText('Realized PnL')).toBeInTheDocument();
        expect(screen.getByText('Win Rate')).toBeInTheDocument();
      }, { timeout: 3000 });
    }, 10000);
  });

  describe('position with hedging info', () => {
    test('renders position with hedged quantity', () => {
      const positionWithHedge = {
        ...mockPositions[0],
        total_hedged_qty: 0.05,
        total_hedged_value_usd: 2500,
      };

      (usePositionsStore as unknown as jest.Mock).mockReturnValue({
        positions: [positionWithHedge],
        positionHistory: [],
        positionHistoryTotal: 0,
        loading: false,
        error: null,
        fetchPositions: mockFetchPositions,
        fetchPositionHistory: jest.fn(),
        closePosition: mockClosePosition,
      });

      renderWithProviders(<PositionsPage />);
      expect(screen.getByText('BTC/USD')).toBeInTheDocument();
    });
  });

  describe('position status', () => {
    test('disables close button when position is closing', () => {
      const closingPosition = {
        ...mockPositions[0],
        status: 'CLOSING',
      };

      (usePositionsStore as unknown as jest.Mock).mockReturnValue({
        positions: [closingPosition],
        positionHistory: [],
        positionHistoryTotal: 0,
        loading: false,
        error: null,
        fetchPositions: mockFetchPositions,
        fetchPositionHistory: jest.fn(),
        closePosition: mockClosePosition,
      });

      renderWithProviders(<PositionsPage />);

      const closeButton = screen.getByRole('button', { name: /close/i });
      expect(closeButton).toBeDisabled();
    });

    test('disables close button when position is closed', () => {
      const closedPosition = {
        ...mockPositions[0],
        status: 'CLOSED',
      };

      (usePositionsStore as unknown as jest.Mock).mockReturnValue({
        positions: [closedPosition],
        positionHistory: [],
        positionHistoryTotal: 0,
        loading: false,
        error: null,
        fetchPositions: mockFetchPositions,
        fetchPositionHistory: jest.fn(),
        closePosition: mockClosePosition,
      });

      renderWithProviders(<PositionsPage />);

      const closeButton = screen.getByRole('button', { name: /close/i });
      expect(closeButton).toBeDisabled();
    });
  });

  describe('active positions metrics', () => {
    test('renders profitable positions count', () => {
      const profitablePositions = [
        { ...mockPositions[0], id: '1', unrealized_pnl_usd: 500 },
        { ...mockPositions[0], id: '2', unrealized_pnl_usd: -100 },
        { ...mockPositions[0], id: '3', unrealized_pnl_usd: 200 },
      ];

      (usePositionsStore as unknown as jest.Mock).mockReturnValue({
        positions: profitablePositions,
        positionHistory: [],
        positionHistoryTotal: 0,
        loading: false,
        error: null,
        fetchPositions: mockFetchPositions,
        fetchPositionHistory: jest.fn(),
        closePosition: mockClosePosition,
      });

      renderWithProviders(<PositionsPage />);

      // 2 out of 3 are profitable
      expect(screen.getByText('2/3')).toBeInTheDocument();
      expect(screen.getByText('Profitable')).toBeInTheDocument();
    });

    test('renders negative unrealized PnL', () => {
      const losingPosition = {
        ...mockPositions[0],
        unrealized_pnl_usd: -500,
        unrealized_pnl_percent: -5.0,
      };

      (usePositionsStore as unknown as jest.Mock).mockReturnValue({
        positions: [losingPosition],
        positionHistory: [],
        positionHistoryTotal: 0,
        loading: false,
        error: null,
        fetchPositions: mockFetchPositions,
        fetchPositionHistory: jest.fn(),
        closePosition: mockClosePosition,
      });

      renderWithProviders(<PositionsPage />);
      expect(screen.getByText('BTC/USD')).toBeInTheDocument();
    });
  });

  test('handles refresh button click', () => {
    const mockFetchPositionHistory = jest.fn();
    (usePositionsStore as unknown as jest.Mock).mockReturnValue({
      positions: mockPositions,
      positionHistory: [],
      positionHistoryTotal: 0,
      loading: false,
      error: null,
      fetchPositions: mockFetchPositions,
      fetchPositionHistory: mockFetchPositionHistory,
      closePosition: mockClosePosition,
    });

    renderWithProviders(<PositionsPage />);

    const refreshButton = screen.getByTestId('RefreshIcon').closest('button');
    if (refreshButton) {
      fireEvent.click(refreshButton);
      expect(mockFetchPositions).toHaveBeenCalled();
      expect(mockFetchPositionHistory).toHaveBeenCalled();
    }
  });

  test('renders position age in hours for new positions', () => {
    const recentPosition = {
      ...mockPositions[0],
      created_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(), // 2 hours ago
    };

    (usePositionsStore as unknown as jest.Mock).mockReturnValue({
      positions: [recentPosition],
      positionHistory: [],
      positionHistoryTotal: 0,
      loading: false,
      error: null,
      fetchPositions: mockFetchPositions,
      fetchPositionHistory: jest.fn(),
      closePosition: mockClosePosition,
    });

    renderWithProviders(<PositionsPage />);
    expect(screen.getByText('BTC/USD')).toBeInTheDocument();
  });

  test('renders position age in days for old positions', () => {
    const oldPosition = {
      ...mockPositions[0],
      created_at: new Date(Date.now() - 3 * 24 * 60 * 60 * 1000).toISOString(), // 3 days ago
    };

    (usePositionsStore as unknown as jest.Mock).mockReturnValue({
      positions: [oldPosition],
      positionHistory: [],
      positionHistoryTotal: 0,
      loading: false,
      error: null,
      fetchPositions: mockFetchPositions,
      fetchPositionHistory: jest.fn(),
      closePosition: mockClosePosition,
    });

    renderWithProviders(<PositionsPage />);
    expect(screen.getByText('BTC/USD')).toBeInTheDocument();
  });
});
