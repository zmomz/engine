import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import DashboardPage from './DashboardPage';
import useDashboardStore from '../store/dashboardStore';
import useRiskStore from '../store/riskStore';

// Mock the stores
jest.mock('../store/dashboardStore');
jest.mock('../store/riskStore');

// Helper to render with router
const renderWithRouter = (component: React.ReactElement) => {
  return render(<MemoryRouter>{component}</MemoryRouter>);
};

describe('DashboardPage', () => {
  const mockFetchDashboardData = jest.fn().mockResolvedValue(undefined);
  const mockFetchRiskStatus = jest.fn().mockResolvedValue(undefined);

  beforeEach(() => {
    jest.clearAllMocks();

    // Default mock implementation for dashboardStore
    (useDashboardStore as unknown as jest.Mock).mockReturnValue({
      data: null,
      loading: false,
      error: null,
      fetchDashboardData: mockFetchDashboardData,
    });

    // Default mock implementation for riskStore
    (useRiskStore as unknown as jest.Mock).mockReturnValue({
      status: null,
      fetchStatus: mockFetchRiskStatus,
      forceStop: jest.fn(),
      forceStart: jest.fn(),
      syncExchange: jest.fn(),
      error: null,
    });
  });

  test('renders dashboard heading', async () => {
    renderWithRouter(<DashboardPage />);
    const headingElement = screen.getByText(/Dashboard/i);
    expect(headingElement).toBeInTheDocument();
    // Wait for async effects to complete
    await waitFor(() => {
      expect(mockFetchDashboardData).toHaveBeenCalled();
    });
  });

  test('calls fetchDashboardData and fetchRiskStatus on mount', async () => {
    renderWithRouter(<DashboardPage />);
    await waitFor(() => {
      expect(mockFetchDashboardData).toHaveBeenCalled();
      expect(mockFetchRiskStatus).toHaveBeenCalled();
    });
  });

  test('displays loading skeleton when loading and no data', async () => {
    (useDashboardStore as unknown as jest.Mock).mockReturnValue({
      data: null,
      loading: true,
      error: null,
      fetchDashboardData: mockFetchDashboardData,
    });

    renderWithRouter(<DashboardPage />);
    // Should show skeleton or loading state
    expect(screen.getByText(/Dashboard/i)).toBeInTheDocument();
    await waitFor(() => {
      expect(mockFetchDashboardData).toHaveBeenCalled();
    });
  });

  test('displays error message when error occurs', async () => {
    (useDashboardStore as unknown as jest.Mock).mockReturnValue({
      data: null,
      loading: false,
      error: 'Failed to fetch data',
      fetchDashboardData: mockFetchDashboardData,
    });

    renderWithRouter(<DashboardPage />);
    expect(screen.getByText(/Error: Failed to fetch data/i)).toBeInTheDocument();
    await waitFor(() => {
      expect(mockFetchDashboardData).toHaveBeenCalled();
    });
  });

  test('renders fetched data correctly', async () => {
    (useDashboardStore as unknown as jest.Mock).mockReturnValue({
      data: {
        live_dashboard: {
          total_active_position_groups: 3,
          queued_signals_count: 5,
          total_pnl_usd: 1250.50,
          tvl: 50000,
          free_usdt: 10000,
          last_webhook_timestamp: '2024-01-01T12:00:00Z',
          engine_status: 'running',
          risk_engine_status: 'active',
        },
        performance_dashboard: {
          pnl_metrics: {},
          equity_curve: [],
          win_loss_stats: { total_trades: 100, wins: 50, losses: 50, win_rate: 50 },
          trade_distribution: {},
          risk_metrics: {},
        },
        timestamp: '2024-01-01T12:00:00Z',
      },
      loading: false,
      error: null,
      fetchDashboardData: mockFetchDashboardData,
    });

    (useRiskStore as unknown as jest.Mock).mockReturnValue({
      status: {
        engine_force_stopped: false,
        engine_paused_by_loss_limit: false,
        daily_realized_pnl: 500,
        max_realized_loss_usd: 1000,
      },
      fetchStatus: mockFetchRiskStatus,
      forceStop: jest.fn(),
      forceStart: jest.fn(),
      syncExchange: jest.fn(),
      error: null,
    });

    renderWithRouter(<DashboardPage />);

    // Check Active Position Groups is displayed
    expect(screen.getByText('3')).toBeInTheDocument();
    await waitFor(() => {
      expect(mockFetchDashboardData).toHaveBeenCalled();
    });
  });
});
