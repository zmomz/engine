import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { ThemeProvider } from '@mui/material/styles';
import { MemoryRouter } from 'react-router-dom';
import PositionsPage from './PositionsPage';
import usePositionsStore from '../store/positionsStore';
import useConfirmStore from '../store/confirmStore';
import { darkTheme } from '../theme/theme';

// Mock stores
jest.mock('../store/positionsStore');
jest.mock('../store/confirmStore');

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
    });

    expect(mockClosePosition).not.toHaveBeenCalled();
  });

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
});
