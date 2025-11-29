import React from 'react';
import { render, screen } from '@testing-library/react';
import DashboardPage from './DashboardPage';
import useEngineStore from '../store/engineStore';

// Mock the store
jest.mock('../store/engineStore');

// Mock child components if complex, but simple ones like Cards can be rendered
// However, to isolate DashboardPage logic, we can mock the store return values.

describe('DashboardPage', () => {
  const mockFetchEngineData = jest.fn();

  beforeEach(() => {
    // Reset mocks before each test
    jest.clearAllMocks();
    
    // Default mock implementation
    (useEngineStore as unknown as jest.Mock).mockReturnValue({
      tvl: null,
      pnl: null,
      realized_pnl: null,
      unrealized_pnl: null,
      activeGroupsCount: null,
      free_usdt: null,
      total_trades: 0,
      total_winning_trades: 0,
      total_losing_trades: 0,
      win_rate: 0,
      fetchEngineData: mockFetchEngineData,
    });
  });

  test('renders dashboard heading', () => {
    render(<DashboardPage />);
    const headingElement = screen.getByText(/Dashboard/i);
    expect(headingElement).toBeInTheDocument();
  });

  test('calls fetchEngineData on mount', () => {
    render(<DashboardPage />);
    expect(mockFetchEngineData).toHaveBeenCalledTimes(1);
  });

  test('displays loading states when data is null', () => {
    render(<DashboardPage />);
    
    // TvlGauge, PnlCard, ActiveGroupsWidget all show 'Loading...' or similar or 0/null state
    // Based on component code read:
    // ActiveGroupsWidget: 'Loading...'
    // PnlCard: 'Loading...'
    
    const loadingElements = screen.getAllByText(/Loading.../i);
    expect(loadingElements.length).toBeGreaterThanOrEqual(1);
  });

  test('renders fetched data correctly', () => {
    (useEngineStore as unknown as jest.Mock).mockReturnValue({
      tvl: 50000,
      pnl: 1250.50,
      realized_pnl: 1000,
      unrealized_pnl: 250.50,
      activeGroupsCount: 3,
      free_usdt: 10000,
      total_trades: 100,
      total_winning_trades: 50,
      total_losing_trades: 50,
      win_rate: 50,
      fetchEngineData: mockFetchEngineData,
    });

    render(<DashboardPage />);

    // Check Active Groups
    expect(screen.getByText('3')).toBeInTheDocument();
    
    // Check PnL (formatted as currency)
    expect(screen.getByText('$1,250.50')).toBeInTheDocument();
    
    // Check TVL (assuming TvlGauge renders the number somewhere or we check PnlCard logic)
    // Note: We didn't read TvlGauge but PnlCard formats currency.
  });

  test('renders negative PnL with correct formatting', () => {
    (useEngineStore as unknown as jest.Mock).mockReturnValue({
      tvl: 50000,
      pnl: -500.25,
      realized_pnl: -600,
      unrealized_pnl: 99.75,
      activeGroupsCount: 1,
      free_usdt: 10000,
      total_trades: 10,
      total_winning_trades: 0,
      total_losing_trades: 10,
      win_rate: 0,
      fetchEngineData: mockFetchEngineData,
    });

    render(<DashboardPage />);
    expect(screen.getByText('$-500.25')).toBeInTheDocument();
  });
});
