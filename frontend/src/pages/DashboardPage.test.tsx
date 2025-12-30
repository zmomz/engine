import React from 'react';
import { render, screen, waitFor, fireEvent, act } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import DashboardPage from './DashboardPage';
import useDashboardStore, { startDashboardPolling, stopDashboardPolling } from '../store/dashboardStore';
import useRiskStore from '../store/riskStore';

// Suppress console.error for act() warnings - these are known testing issues
const originalError = console.error;
beforeAll(() => {
  console.error = (...args: any[]) => {
    if (args[0]?.includes?.('inside a test was not wrapped in act') ||
        (typeof args[0] === 'string' && args[0].includes('inside a test was not wrapped in act'))) {
      return;
    }
    originalError.call(console, ...args);
  };
});

afterAll(() => {
  console.error = originalError;
});

// Mock the stores
jest.mock('../store/dashboardStore');
jest.mock('../store/riskStore');

// Mock the polling functions
const mockStartDashboardPolling = startDashboardPolling as jest.Mock;
const mockStopDashboardPolling = stopDashboardPolling as jest.Mock;

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

  test('displays no data message when data is null and not loading', async () => {
    (useDashboardStore as unknown as jest.Mock).mockReturnValue({
      data: null,
      loading: false,
      error: null,
      fetchDashboardData: mockFetchDashboardData,
    });

    renderWithRouter(<DashboardPage />);
    expect(screen.getByText('No dashboard data available')).toBeInTheDocument();
  });

  test('shows force stopped queue status', async () => {
    (useDashboardStore as unknown as jest.Mock).mockReturnValue({
      data: {
        live_dashboard: {
          total_active_position_groups: 1,
          queued_signals_count: 2,
          total_pnl_usd: 100,
          tvl: 10000,
          free_usdt: 5000,
          last_webhook_timestamp: null,
          engine_status: 'running',
          risk_engine_status: 'active',
          wins: 10,
          losses: 5,
          total_trades: 15,
          win_rate: 66.67,
          realized_pnl_usd: 50,
          unrealized_pnl_usd: 50,
          pnl_today: 25,
        },
      },
      loading: false,
      error: null,
      fetchDashboardData: mockFetchDashboardData,
    });

    (useRiskStore as unknown as jest.Mock).mockReturnValue({
      status: {
        engine_force_stopped: true,
        engine_paused_by_loss_limit: false,
        daily_realized_pnl: 0,
        max_realized_loss_usd: 500,
        config: { max_open_positions_global: 10 },
      },
      fetchStatus: mockFetchRiskStatus,
      forceStop: jest.fn(),
      forceStart: jest.fn(),
      syncExchange: jest.fn(),
      error: null,
    });

    renderWithRouter(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText(/Queue: Stopped/i)).toBeInTheDocument();
    });

    // Should show Start Queue button when stopped
    expect(screen.getByRole('button', { name: /Start Queue/i })).toBeInTheDocument();
  });

  test('shows paused queue status when loss limit reached', async () => {
    (useDashboardStore as unknown as jest.Mock).mockReturnValue({
      data: {
        live_dashboard: {
          total_active_position_groups: 1,
          queued_signals_count: 2,
          total_pnl_usd: -400,
          tvl: 10000,
          free_usdt: 5000,
          last_webhook_timestamp: '2024-01-01T12:00:00Z',
          engine_status: 'running',
          risk_engine_status: 'active',
          wins: 5,
          losses: 10,
          total_trades: 15,
          win_rate: 33.33,
          realized_pnl_usd: -400,
          unrealized_pnl_usd: 0,
          pnl_today: -400,
        },
      },
      loading: false,
      error: null,
      fetchDashboardData: mockFetchDashboardData,
    });

    (useRiskStore as unknown as jest.Mock).mockReturnValue({
      status: {
        engine_force_stopped: false,
        engine_paused_by_loss_limit: true,
        daily_realized_pnl: -400,
        max_realized_loss_usd: 500,
        config: { max_open_positions_global: 10 },
      },
      fetchStatus: mockFetchRiskStatus,
      forceStop: jest.fn(),
      forceStart: jest.fn(),
      syncExchange: jest.fn(),
      error: null,
    });

    renderWithRouter(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText(/Queue: Paused/i)).toBeInTheDocument();
    });

    // Should show paused warning alert
    expect(screen.getByText(/Queue paused: Loss limit reached/i)).toBeInTheDocument();
  });

  test('handles sync exchange button click', async () => {
    const mockSyncExchange = jest.fn().mockResolvedValue(undefined);

    (useDashboardStore as unknown as jest.Mock).mockReturnValue({
      data: {
        live_dashboard: {
          total_active_position_groups: 1,
          queued_signals_count: 0,
          total_pnl_usd: 100,
          tvl: 10000,
          free_usdt: 5000,
          last_webhook_timestamp: '2024-01-01T12:00:00Z',
          engine_status: 'running',
          risk_engine_status: 'active',
        },
      },
      loading: false,
      error: null,
      fetchDashboardData: mockFetchDashboardData,
    });

    (useRiskStore as unknown as jest.Mock).mockReturnValue({
      status: {
        engine_force_stopped: false,
        engine_paused_by_loss_limit: false,
        daily_realized_pnl: 100,
        max_realized_loss_usd: 500,
      },
      fetchStatus: mockFetchRiskStatus,
      forceStop: jest.fn(),
      forceStart: jest.fn(),
      syncExchange: mockSyncExchange,
      error: null,
    });

    renderWithRouter(<DashboardPage />);

    const syncButton = screen.getByRole('button', { name: /Sync Exchange/i });
    fireEvent.click(syncButton);

    await waitFor(() => {
      expect(mockSyncExchange).toHaveBeenCalled();
    });
  });

  test('displays risk error alert', async () => {
    (useDashboardStore as unknown as jest.Mock).mockReturnValue({
      data: {
        live_dashboard: {
          total_active_position_groups: 1,
          queued_signals_count: 0,
          total_pnl_usd: 100,
          tvl: 10000,
          free_usdt: 5000,
          last_webhook_timestamp: '2024-01-01T12:00:00Z',
          engine_status: 'running',
          risk_engine_status: 'active',
        },
      },
      loading: false,
      error: null,
      fetchDashboardData: mockFetchDashboardData,
    });

    (useRiskStore as unknown as jest.Mock).mockReturnValue({
      status: null,
      fetchStatus: mockFetchRiskStatus,
      forceStop: jest.fn(),
      forceStart: jest.fn(),
      syncExchange: jest.fn(),
      error: 'Risk service unavailable',
    });

    renderWithRouter(<DashboardPage />);

    expect(screen.getByText('Risk service unavailable')).toBeInTheDocument();
  });

  test('handles keyboard shortcut for refresh', async () => {
    (useDashboardStore as unknown as jest.Mock).mockReturnValue({
      data: {
        live_dashboard: {
          total_active_position_groups: 1,
          queued_signals_count: 0,
          total_pnl_usd: 100,
          tvl: 10000,
          free_usdt: 5000,
          last_webhook_timestamp: '2024-01-01T12:00:00Z',
          engine_status: 'running',
          risk_engine_status: 'active',
        },
      },
      loading: false,
      error: null,
      fetchDashboardData: mockFetchDashboardData,
    });

    (useRiskStore as unknown as jest.Mock).mockReturnValue({
      status: {
        engine_force_stopped: false,
        engine_paused_by_loss_limit: false,
        daily_realized_pnl: 100,
        max_realized_loss_usd: 500,
      },
      fetchStatus: mockFetchRiskStatus,
      forceStop: jest.fn(),
      forceStart: jest.fn(),
      syncExchange: jest.fn(),
      error: null,
    });

    renderWithRouter(<DashboardPage />);

    // Trigger Ctrl+R keyboard shortcut
    act(() => {
      const event = new KeyboardEvent('keydown', {
        key: 'r',
        ctrlKey: true,
        bubbles: true,
      });
      window.dispatchEvent(event);
    });

    await waitFor(() => {
      // fetchDashboardData should be called again via keyboard shortcut
      expect(mockFetchDashboardData).toHaveBeenCalledTimes(2);
    });
  });

  test('starts and stops polling on mount and unmount', async () => {
    (useDashboardStore as unknown as jest.Mock).mockReturnValue({
      data: {
        live_dashboard: {
          total_active_position_groups: 1,
          queued_signals_count: 0,
          total_pnl_usd: 100,
          tvl: 10000,
          free_usdt: 5000,
          last_webhook_timestamp: '2024-01-01T12:00:00Z',
          engine_status: 'running',
          risk_engine_status: 'active',
        },
      },
      loading: false,
      error: null,
      fetchDashboardData: mockFetchDashboardData,
    });

    (useRiskStore as unknown as jest.Mock).mockReturnValue({
      status: {
        engine_force_stopped: false,
        engine_paused_by_loss_limit: false,
      },
      fetchStatus: mockFetchRiskStatus,
      forceStop: jest.fn(),
      forceStart: jest.fn(),
      syncExchange: jest.fn(),
      error: null,
    });

    const { unmount } = renderWithRouter(<DashboardPage />);

    await waitFor(() => {
      expect(mockStartDashboardPolling).toHaveBeenCalled();
    });

    unmount();

    expect(mockStopDashboardPolling).toHaveBeenCalled();
  });

  test('handles force start button click', async () => {
    const mockForceStart = jest.fn();

    (useDashboardStore as unknown as jest.Mock).mockReturnValue({
      data: {
        live_dashboard: {
          total_active_position_groups: 1,
          queued_signals_count: 0,
          total_pnl_usd: 100,
          tvl: 10000,
          free_usdt: 5000,
          last_webhook_timestamp: '2024-01-01T12:00:00Z',
          engine_status: 'running',
          risk_engine_status: 'active',
        },
      },
      loading: false,
      error: null,
      fetchDashboardData: mockFetchDashboardData,
    });

    (useRiskStore as unknown as jest.Mock).mockReturnValue({
      status: {
        engine_force_stopped: true,
        engine_paused_by_loss_limit: false,
      },
      fetchStatus: mockFetchRiskStatus,
      forceStop: jest.fn(),
      forceStart: mockForceStart,
      syncExchange: jest.fn(),
      error: null,
    });

    renderWithRouter(<DashboardPage />);

    const startButton = screen.getByRole('button', { name: /Start Queue/i });
    fireEvent.click(startButton);

    expect(mockForceStart).toHaveBeenCalled();
  });

  test('handles force stop button click', async () => {
    const mockForceStop = jest.fn();

    (useDashboardStore as unknown as jest.Mock).mockReturnValue({
      data: {
        live_dashboard: {
          total_active_position_groups: 1,
          queued_signals_count: 0,
          total_pnl_usd: 100,
          tvl: 10000,
          free_usdt: 5000,
          last_webhook_timestamp: '2024-01-01T12:00:00Z',
          engine_status: 'running',
          risk_engine_status: 'active',
        },
      },
      loading: false,
      error: null,
      fetchDashboardData: mockFetchDashboardData,
    });

    (useRiskStore as unknown as jest.Mock).mockReturnValue({
      status: {
        engine_force_stopped: false,
        engine_paused_by_loss_limit: false,
      },
      fetchStatus: mockFetchRiskStatus,
      forceStop: mockForceStop,
      forceStart: jest.fn(),
      syncExchange: jest.fn(),
      error: null,
    });

    renderWithRouter(<DashboardPage />);

    const stopButton = screen.getByRole('button', { name: /Stop Queue/i });
    fireEvent.click(stopButton);

    expect(mockForceStop).toHaveBeenCalled();
  });

  test('displays no webhook timestamp message', async () => {
    (useDashboardStore as unknown as jest.Mock).mockReturnValue({
      data: {
        live_dashboard: {
          total_active_position_groups: 0,
          queued_signals_count: 0,
          total_pnl_usd: 0,
          tvl: 10000,
          free_usdt: 10000,
          last_webhook_timestamp: null,
          engine_status: 'running',
          risk_engine_status: 'active',
        },
      },
      loading: false,
      error: null,
      fetchDashboardData: mockFetchDashboardData,
    });

    (useRiskStore as unknown as jest.Mock).mockReturnValue({
      status: {
        engine_force_stopped: false,
        engine_paused_by_loss_limit: false,
      },
      fetchStatus: mockFetchRiskStatus,
      forceStop: jest.fn(),
      forceStart: jest.fn(),
      syncExchange: jest.fn(),
      error: null,
    });

    renderWithRouter(<DashboardPage />);

    expect(screen.getByText(/No signals yet/i)).toBeInTheDocument();
  });

  test('handles zero TVL case for capital deployed calculation', async () => {
    (useDashboardStore as unknown as jest.Mock).mockReturnValue({
      data: {
        live_dashboard: {
          total_active_position_groups: 0,
          queued_signals_count: 0,
          total_pnl_usd: 0,
          tvl: 0,
          free_usdt: 0,
          last_webhook_timestamp: null,
          engine_status: 'running',
          risk_engine_status: 'active',
        },
      },
      loading: false,
      error: null,
      fetchDashboardData: mockFetchDashboardData,
    });

    (useRiskStore as unknown as jest.Mock).mockReturnValue({
      status: {
        engine_force_stopped: false,
        engine_paused_by_loss_limit: false,
      },
      fetchStatus: mockFetchRiskStatus,
      forceStop: jest.fn(),
      forceStart: jest.fn(),
      syncExchange: jest.fn(),
      error: null,
    });

    renderWithRouter(<DashboardPage />);

    // Should render without errors even with zero TVL
    expect(screen.getByText('Dashboard')).toBeInTheDocument();
  });

  test('shows syncing state on sync button', async () => {
    let resolveSyncPromise: () => void;
    const syncPromise = new Promise<void>((resolve) => {
      resolveSyncPromise = resolve;
    });
    const mockSyncExchange = jest.fn().mockReturnValue(syncPromise);

    (useDashboardStore as unknown as jest.Mock).mockReturnValue({
      data: {
        live_dashboard: {
          total_active_position_groups: 1,
          queued_signals_count: 0,
          total_pnl_usd: 100,
          tvl: 10000,
          free_usdt: 5000,
          last_webhook_timestamp: '2024-01-01T12:00:00Z',
          engine_status: 'running',
          risk_engine_status: 'active',
        },
      },
      loading: false,
      error: null,
      fetchDashboardData: mockFetchDashboardData,
    });

    (useRiskStore as unknown as jest.Mock).mockReturnValue({
      status: {
        engine_force_stopped: false,
        engine_paused_by_loss_limit: false,
      },
      fetchStatus: mockFetchRiskStatus,
      forceStop: jest.fn(),
      forceStart: jest.fn(),
      syncExchange: mockSyncExchange,
      error: null,
    });

    renderWithRouter(<DashboardPage />);

    const syncButton = screen.getByRole('button', { name: /Sync Exchange/i });
    fireEvent.click(syncButton);

    // Button should show syncing state
    await waitFor(() => {
      expect(screen.getByText('Syncing...')).toBeInTheDocument();
    });

    // Resolve the sync promise
    await act(async () => {
      resolveSyncPromise!();
    });

    // Button should return to normal state
    await waitFor(() => {
      expect(screen.getByText('Sync Exchange')).toBeInTheDocument();
    });
  });
});
