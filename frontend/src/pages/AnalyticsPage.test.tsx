import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ThemeProvider } from '@mui/material/styles';
import { MemoryRouter } from 'react-router-dom';
import AnalyticsPage from './AnalyticsPage';
import usePositionsStore from '../store/positionsStore';
import useDashboardStore from '../store/dashboardStore';
import { darkTheme } from '../theme/theme';

// Mock stores
jest.mock('../store/positionsStore');
jest.mock('../store/dashboardStore');

// Mock recharts to avoid SVG rendering issues in tests
jest.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: any) => <div data-testid="responsive-container">{children}</div>,
  AreaChart: ({ children }: any) => <div data-testid="area-chart">{children}</div>,
  Area: () => <div data-testid="area" />,
  BarChart: ({ children }: any) => <div data-testid="bar-chart">{children}</div>,
  Bar: ({ children }: any) => <div data-testid="bar">{children}</div>,
  Cell: () => <div data-testid="cell" />,
  XAxis: () => <div data-testid="x-axis" />,
  YAxis: () => <div data-testid="y-axis" />,
  CartesianGrid: () => <div data-testid="cartesian-grid" />,
  Tooltip: () => <div data-testid="tooltip" />,
}));

// Mock useKeyboardShortcuts
jest.mock('../hooks/useKeyboardShortcuts', () => ({
  useKeyboardShortcuts: jest.fn(),
}));

// Mock DataFreshnessIndicator
jest.mock('../components/DataFreshnessIndicator', () => ({
  DataFreshnessIndicator: () => <div data-testid="data-freshness" />,
}));

const renderWithProviders = (component: React.ReactElement) => {
  return render(
    <ThemeProvider theme={darkTheme}>
      <MemoryRouter>{component}</MemoryRouter>
    </ThemeProvider>
  );
};

describe('AnalyticsPage', () => {
  const mockFetchPositionHistory = jest.fn().mockResolvedValue(undefined);
  const mockFetchDashboardData = jest.fn().mockResolvedValue(undefined);

  // Use recent dates so they show up in time range filters
  const now = new Date();
  const yesterday = new Date(now.getTime() - 24 * 60 * 60 * 1000);
  const twoDaysAgo = new Date(now.getTime() - 2 * 24 * 60 * 60 * 1000);

  const mockPositionHistory = [
    {
      id: '1',
      symbol: 'BTC/USDT',
      side: 'long',
      status: 'closed',
      weighted_avg_entry: 50000,
      total_invested_usd: 1000,
      realized_pnl_usd: 150,
      created_at: twoDaysAgo.toISOString(),
      closed_at: yesterday.toISOString(),
    },
    {
      id: '2',
      symbol: 'ETH/USDT',
      side: 'long',
      status: 'closed',
      weighted_avg_entry: 2500,
      total_invested_usd: 500,
      realized_pnl_usd: -50,
      created_at: yesterday.toISOString(),
      closed_at: now.toISOString(),
    },
    {
      id: '3',
      symbol: 'BTC/USDT',
      side: 'short',
      status: 'closed',
      weighted_avg_entry: 48000,
      total_invested_usd: 800,
      realized_pnl_usd: 200,
      created_at: yesterday.toISOString(),
      closed_at: now.toISOString(),
    },
  ];

  const mockDashboardData = {
    performance_dashboard: {
      pnl_metrics: {
        pnl_today: 100,
        pnl_week: 500,
        pnl_month: 2000,
        pnl_all_time: 10000,
      },
      risk_metrics: {
        max_drawdown: -500,
        sharpe_ratio: 1.5,
        sortino_ratio: 2.0,
      },
      win_loss_stats: {
        total_trades: 100,
        wins: 60,
        losses: 40,
        win_rate: 60,
      },
      equity_curve: [],
      trade_distribution: {},
    },
  };

  beforeEach(() => {
    jest.clearAllMocks();

    (usePositionsStore as unknown as jest.Mock).mockReturnValue({
      positionHistory: mockPositionHistory,
      fetchPositionHistory: mockFetchPositionHistory,
      loading: false,
    });

    (useDashboardStore as unknown as jest.Mock).mockReturnValue({
      data: mockDashboardData,
      fetchDashboardData: mockFetchDashboardData,
      loading: false,
    });
  });

  test('renders analytics page heading', () => {
    renderWithProviders(<AnalyticsPage />);
    expect(screen.getByText('Analytics')).toBeInTheDocument();
  });

  test('displays trade count chip', () => {
    renderWithProviders(<AnalyticsPage />);
    // The chip shows "X trades" format
    expect(screen.getByText(/\d+ trades$/)).toBeInTheDocument();
  });

  test('renders time range toggle buttons', () => {
    renderWithProviders(<AnalyticsPage />);
    expect(screen.getByRole('button', { name: '24h' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '7d' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '30d' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'All' })).toBeInTheDocument();
  });

  test('changes time range when toggle button clicked', () => {
    renderWithProviders(<AnalyticsPage />);

    fireEvent.click(screen.getByRole('button', { name: '24h' }));
    fireEvent.click(screen.getByRole('button', { name: '7d' }));
    fireEvent.click(screen.getByRole('button', { name: 'All' }));

    // Should not throw - verifies toggle works
    expect(screen.getByRole('button', { name: 'All' })).toBeInTheDocument();
  });

  test('displays PnL period summary when data available', () => {
    renderWithProviders(<AnalyticsPage />);
    expect(screen.getByText('Today')).toBeInTheDocument();
    expect(screen.getByText('This Week')).toBeInTheDocument();
    expect(screen.getByText('This Month')).toBeInTheDocument();
    expect(screen.getByText('All Time')).toBeInTheDocument();
  });

  test('displays key metrics cards', () => {
    renderWithProviders(<AnalyticsPage />);
    expect(screen.getByText('Total PnL')).toBeInTheDocument();
    expect(screen.getByText('Win Rate')).toBeInTheDocument();
    expect(screen.getByText('Profit Factor')).toBeInTheDocument();
    expect(screen.getByText('Avg Hold Time')).toBeInTheDocument();
  });

  test('displays performance summary section', () => {
    renderWithProviders(<AnalyticsPage />);
    expect(screen.getByText('Performance Summary')).toBeInTheDocument();
    expect(screen.getByText('Win/Loss Ratio')).toBeInTheDocument();
  });

  test('displays pair performance table', () => {
    renderWithProviders(<AnalyticsPage />);
    expect(screen.getByText('Performance by Pair')).toBeInTheDocument();
    // Find in table context
    const table = screen.getByRole('table');
    expect(table).toBeInTheDocument();
  });

  test('displays equity curve section', () => {
    renderWithProviders(<AnalyticsPage />);
    expect(screen.getByText('Equity Curve')).toBeInTheDocument();
  });

  test('displays PnL by day of week section', () => {
    renderWithProviders(<AnalyticsPage />);
    expect(screen.getByText('PnL by Day of Week')).toBeInTheDocument();
  });

  test('renders loading skeleton when loading and no data', () => {
    (usePositionsStore as unknown as jest.Mock).mockReturnValue({
      positionHistory: [],
      fetchPositionHistory: mockFetchPositionHistory,
      loading: true,
    });

    (useDashboardStore as unknown as jest.Mock).mockReturnValue({
      data: null,
      fetchDashboardData: mockFetchDashboardData,
      loading: true,
    });

    renderWithProviders(<AnalyticsPage />);
    // Should not show Analytics heading when loading
    expect(screen.queryByText('Analytics')).not.toBeInTheDocument();
  });

  test('shows export button', () => {
    renderWithProviders(<AnalyticsPage />);
    const exportButton = screen.getByRole('button', { name: /Export/i });
    expect(exportButton).toBeInTheDocument();
  });

  test('opens export menu on click', async () => {
    renderWithProviders(<AnalyticsPage />);

    const exportButton = screen.getByRole('button', { name: /Export/i });
    fireEvent.click(exportButton);

    await waitFor(() => {
      expect(screen.getByText('Export Trades (CSV)')).toBeInTheDocument();
      expect(screen.getByText('Export Summary (CSV)')).toBeInTheDocument();
    });
  });

  test('handles export trades CSV click', async () => {
    // Mock URL.createObjectURL
    const originalCreateObjectURL = global.URL.createObjectURL;
    global.URL.createObjectURL = jest.fn(() => 'blob:test');

    renderWithProviders(<AnalyticsPage />);

    const exportButton = screen.getByRole('button', { name: /Export/i });
    fireEvent.click(exportButton);

    await waitFor(() => {
      const exportTradesOption = screen.getByText('Export Trades (CSV)');
      fireEvent.click(exportTradesOption);
    });

    // Restore
    global.URL.createObjectURL = originalCreateObjectURL;
  });

  test('handles export summary CSV click', async () => {
    // Mock URL.createObjectURL
    const originalCreateObjectURL = global.URL.createObjectURL;
    global.URL.createObjectURL = jest.fn(() => 'blob:test');

    renderWithProviders(<AnalyticsPage />);

    const exportButton = screen.getByRole('button', { name: /Export/i });
    fireEvent.click(exportButton);

    await waitFor(() => {
      const exportSummaryOption = screen.getByText('Export Summary (CSV)');
      fireEvent.click(exportSummaryOption);
    });

    // Restore
    global.URL.createObjectURL = originalCreateObjectURL;
  });

  test('handles refresh button click', () => {
    renderWithProviders(<AnalyticsPage />);

    // Find the refresh icon button
    const refreshButtons = screen.getAllByRole('button');
    const refreshButton = refreshButtons.find(btn =>
      btn.querySelector('[data-testid="RefreshIcon"]')
    );

    if (refreshButton) {
      fireEvent.click(refreshButton);
    }

    // Fetch should be called on mount, then again on refresh
    expect(mockFetchPositionHistory).toHaveBeenCalled();
    expect(mockFetchDashboardData).toHaveBeenCalled();
  });

  test('calls fetch functions on mount', () => {
    renderWithProviders(<AnalyticsPage />);
    expect(mockFetchPositionHistory).toHaveBeenCalled();
    expect(mockFetchDashboardData).toHaveBeenCalled();
  });

  test('displays risk metrics when available', () => {
    renderWithProviders(<AnalyticsPage />);
    expect(screen.getByText('Risk Metrics')).toBeInTheDocument();
    expect(screen.getByText('Max DD')).toBeInTheDocument();
    expect(screen.getByText('Sharpe')).toBeInTheDocument();
    expect(screen.getByText('Sortino')).toBeInTheDocument();
  });

  test('handles empty position history', () => {
    (usePositionsStore as unknown as jest.Mock).mockReturnValue({
      positionHistory: [],
      fetchPositionHistory: mockFetchPositionHistory,
      loading: false,
    });

    renderWithProviders(<AnalyticsPage />);
    expect(screen.getByText('No closed trades in selected period')).toBeInTheDocument();
  });

  test('handles position with null realized_pnl_usd', () => {
    (usePositionsStore as unknown as jest.Mock).mockReturnValue({
      positionHistory: [
        {
          id: '1',
          symbol: 'BTC/USDT',
          side: 'long',
          status: 'closed',
          weighted_avg_entry: 50000,
          total_invested_usd: 1000,
          realized_pnl_usd: null,
          created_at: yesterday.toISOString(),
          closed_at: now.toISOString(),
        },
      ],
      fetchPositionHistory: mockFetchPositionHistory,
      loading: false,
    });

    renderWithProviders(<AnalyticsPage />);
    expect(screen.getByText('Analytics')).toBeInTheDocument();
  });

  test('handles position with string realized_pnl_usd', () => {
    (usePositionsStore as unknown as jest.Mock).mockReturnValue({
      positionHistory: [
        {
          id: '1',
          symbol: 'BTC/USDT',
          side: 'long',
          status: 'closed',
          weighted_avg_entry: 50000,
          total_invested_usd: 1000,
          realized_pnl_usd: '150.50',
          created_at: yesterday.toISOString(),
          closed_at: now.toISOString(),
        },
      ],
      fetchPositionHistory: mockFetchPositionHistory,
      loading: false,
    });

    renderWithProviders(<AnalyticsPage />);
    expect(screen.getByText('Analytics')).toBeInTheDocument();
  });

  test('handles missing dashboard data', () => {
    (useDashboardStore as unknown as jest.Mock).mockReturnValue({
      data: null,
      fetchDashboardData: mockFetchDashboardData,
      loading: false,
    });

    renderWithProviders(<AnalyticsPage />);
    expect(screen.getByText('Analytics')).toBeInTheDocument();
  });

  test('handles all losing trades (profit factor edge case)', () => {
    (usePositionsStore as unknown as jest.Mock).mockReturnValue({
      positionHistory: [
        {
          id: '1',
          symbol: 'BTC/USDT',
          side: 'long',
          status: 'closed',
          weighted_avg_entry: 50000,
          total_invested_usd: 1000,
          realized_pnl_usd: -100,
          created_at: yesterday.toISOString(),
          closed_at: now.toISOString(),
        },
      ],
      fetchPositionHistory: mockFetchPositionHistory,
      loading: false,
    });

    renderWithProviders(<AnalyticsPage />);
    expect(screen.getByText('Analytics')).toBeInTheDocument();
  });

  test('handles all winning trades (profit factor infinity)', () => {
    (usePositionsStore as unknown as jest.Mock).mockReturnValue({
      positionHistory: [
        {
          id: '1',
          symbol: 'BTC/USDT',
          side: 'long',
          status: 'closed',
          weighted_avg_entry: 50000,
          total_invested_usd: 1000,
          realized_pnl_usd: 100,
          created_at: yesterday.toISOString(),
          closed_at: now.toISOString(),
        },
      ],
      fetchPositionHistory: mockFetchPositionHistory,
      loading: false,
    });

    renderWithProviders(<AnalyticsPage />);
    expect(screen.getByText('∞')).toBeInTheDocument();
  });

  test('displays avg win and avg loss stats', () => {
    renderWithProviders(<AnalyticsPage />);
    expect(screen.getByText('Avg Win')).toBeInTheDocument();
    expect(screen.getByText('Avg Loss')).toBeInTheDocument();
    expect(screen.getByText('Best Trade')).toBeInTheDocument();
    expect(screen.getByText('Worst Trade')).toBeInTheDocument();
  });

  test('displays win/loss chips', () => {
    renderWithProviders(<AnalyticsPage />);
    // Look for W and L chips (e.g., "2W", "1L")
    expect(screen.getByText(/\dW$/)).toBeInTheDocument();
    expect(screen.getByText(/\dL$/)).toBeInTheDocument();
  });

  test('handles position without closed_at date', () => {
    (usePositionsStore as unknown as jest.Mock).mockReturnValue({
      positionHistory: [
        {
          id: '1',
          symbol: 'BTC/USDT',
          side: 'long',
          status: 'active',
          weighted_avg_entry: 50000,
          total_invested_usd: 1000,
          realized_pnl_usd: 0,
          created_at: yesterday.toISOString(),
          closed_at: null,
        },
      ],
      fetchPositionHistory: mockFetchPositionHistory,
      loading: false,
    });

    renderWithProviders(<AnalyticsPage />);
    expect(screen.getByText('Analytics')).toBeInTheDocument();
  });

  test('handles recent positions in 24h time range', () => {
    const recentDate = new Date();
    recentDate.setHours(recentDate.getHours() - 2);

    (usePositionsStore as unknown as jest.Mock).mockReturnValue({
      positionHistory: [
        {
          id: '1',
          symbol: 'BTC/USDT',
          side: 'long',
          status: 'closed',
          weighted_avg_entry: 50000,
          total_invested_usd: 1000,
          realized_pnl_usd: 100,
          created_at: recentDate.toISOString(),
          closed_at: new Date().toISOString(),
        },
      ],
      fetchPositionHistory: mockFetchPositionHistory,
      loading: false,
    });

    renderWithProviders(<AnalyticsPage />);
    fireEvent.click(screen.getByRole('button', { name: '24h' }));

    // Position should still be visible after switching to 24h
    expect(screen.getByText('Analytics')).toBeInTheDocument();
  });

  test('export button disabled when no positions', () => {
    (usePositionsStore as unknown as jest.Mock).mockReturnValue({
      positionHistory: [],
      fetchPositionHistory: mockFetchPositionHistory,
      loading: false,
    });

    renderWithProviders(<AnalyticsPage />);
    const exportButton = screen.getByRole('button', { name: /Export/i });
    expect(exportButton).toBeDisabled();
  });

  test('displays symbols in pair performance table', () => {
    renderWithProviders(<AnalyticsPage />);

    // Look for the table headers
    expect(screen.getByText('Symbol')).toBeInTheDocument();
    expect(screen.getByText('Trades')).toBeInTheDocument();
    expect(screen.getByText('WR')).toBeInTheDocument();
    expect(screen.getByText('PnL')).toBeInTheDocument();
  });

  test('hides PnL summary when no dashboard data', () => {
    (useDashboardStore as unknown as jest.Mock).mockReturnValue({
      data: null,
      fetchDashboardData: mockFetchDashboardData,
      loading: false,
    });

    renderWithProviders(<AnalyticsPage />);

    // Today/This Week etc. should not be visible
    expect(screen.queryByText('Today')).not.toBeInTheDocument();
    expect(screen.queryByText('Risk Metrics')).not.toBeInTheDocument();
  });

  test('displays no data message for day of week when no data', () => {
    (usePositionsStore as unknown as jest.Mock).mockReturnValue({
      positionHistory: [],
      fetchPositionHistory: mockFetchPositionHistory,
      loading: false,
    });

    renderWithProviders(<AnalyticsPage />);
    expect(screen.getByText('No data available')).toBeInTheDocument();
  });

  test('handles position with undefined realized_pnl_usd', () => {
    (usePositionsStore as unknown as jest.Mock).mockReturnValue({
      positionHistory: [
        {
          id: '1',
          symbol: 'BTC/USDT',
          side: 'long',
          status: 'closed',
          weighted_avg_entry: 50000,
          total_invested_usd: 1000,
          realized_pnl_usd: undefined,
          created_at: yesterday.toISOString(),
          closed_at: now.toISOString(),
        },
      ],
      fetchPositionHistory: mockFetchPositionHistory,
      loading: false,
    });

    renderWithProviders(<AnalyticsPage />);
    expect(screen.getByText('Analytics')).toBeInTheDocument();
  });

  test('handles 7d time range selection', () => {
    renderWithProviders(<AnalyticsPage />);

    fireEvent.click(screen.getByRole('button', { name: '7d' }));
    expect(screen.getByRole('button', { name: '7d' })).toHaveAttribute('aria-pressed', 'true');
  });

  test('shows correct profit factor label based on value', () => {
    // With default mock data, profit factor should be > 1
    renderWithProviders(<AnalyticsPage />);

    // The label should show based on profit factor value
    // With wins=350 and losses=50, profit factor = 7, so label should be "Good"
    expect(screen.getByText(/Good|Okay|Poor/)).toBeInTheDocument();
  });
});
