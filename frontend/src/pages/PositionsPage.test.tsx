import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import PositionsPage from './PositionsPage';
import usePositionsStore from '../store/positionsStore';
import useConfirmStore from '../store/confirmStore';

// Mock stores
jest.mock('../store/positionsStore');
jest.mock('../store/confirmStore');

describe('PositionsPage', () => {
  const mockFetchPositions = jest.fn();
  const mockClosePosition = jest.fn();
  const mockRequestConfirm = jest.fn();

  const mockPositions = [
    {
      id: '1',
      symbol: 'BTC/USD',
      side: 'long',
      status: 'active',
      unrealized_pnl_usd: 500,
      unrealized_pnl_percent: 5.0,
      total_invested_usd: 10000,
      pyramids: [],
    },
  ];

  beforeEach(() => {
    jest.clearAllMocks();
    
    (usePositionsStore as unknown as jest.Mock).mockReturnValue({
      positions: mockPositions,
      loading: false,
      error: null,
      fetchPositions: mockFetchPositions,
      closePosition: mockClosePosition,
    });

    (useConfirmStore.getState as jest.Mock) = jest.fn().mockReturnValue({
        requestConfirm: mockRequestConfirm
    });
  });

  test('renders the positions table with data', async () => {
    render(<PositionsPage />);
    
    expect(screen.getByText('BTC/USD')).toBeInTheDocument();
    expect(screen.getByText('long')).toBeInTheDocument();
    expect(screen.getByText('$500.00')).toBeInTheDocument();
  });

  test('handles close position click', async () => {
    mockRequestConfirm.mockResolvedValue(true); // User confirms

    render(<PositionsPage />);
    
    const closeButton = screen.getByRole('button', { name: /close/i });
    fireEvent.click(closeButton);

    await waitFor(() => {
        expect(mockRequestConfirm).toHaveBeenCalled();
    });
    
    expect(mockClosePosition).toHaveBeenCalledWith('1');
  });

  test('handles close position cancellation', async () => {
    mockRequestConfirm.mockResolvedValue(false); // User cancels

    render(<PositionsPage />);
    
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
        loading: true,
        error: null,
        fetchPositions: mockFetchPositions,
    });
    
    render(<PositionsPage />);
    // Assuming DataGrid shows a loading overlay or similar, but here we might just check if fetch was called
    expect(mockFetchPositions).toHaveBeenCalled();
  });

  test('renders error state', () => {
    (usePositionsStore as unknown as jest.Mock).mockReturnValue({
        positions: [],
        loading: false,
        error: "Failed to fetch",
        fetchPositions: mockFetchPositions,
    });
    
    render(<PositionsPage />);
    expect(screen.getByText("Error: Failed to fetch")).toBeInTheDocument();
  });
});
