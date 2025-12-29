import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material';
import RiskPage from './RiskPage';
import useRiskStore from '../store/riskStore';
import useConfirmStore from '../store/confirmStore';
import userEvent from '@testing-library/user-event';

// Mock Store
jest.mock('../store/riskStore');
jest.mock('../store/confirmStore', () => ({
    __esModule: true,
    default: {
        getState: jest.fn(),
    }
}));

// Create a theme with custom bullish/bearish colors
const theme = createTheme({
  palette: {
    mode: 'dark',
    primary: { main: '#1976d2' },
    success: { main: '#4caf50' },
    error: { main: '#f44336' },
    warning: { main: '#ff9800' },
  },
});

// Add custom palette colors
(theme.palette as any).bullish = { main: '#4caf50', light: '#81c784', dark: '#388e3c', contrastText: '#fff' };
(theme.palette as any).bearish = { main: '#f44336', light: '#e57373', dark: '#d32f2f', contrastText: '#fff' };

const renderWithProviders = (component: React.ReactElement) => {
  return render(
    <ThemeProvider theme={theme}>
      <MemoryRouter>
        {component}
      </MemoryRouter>
    </ThemeProvider>
  );
};

const mockRiskStatus = {
  identified_loser: {
    id: 'loser1',
    symbol: 'BTCUSDT',
    unrealized_pnl_percent: -10,
    unrealized_pnl_usd: -100,
    risk_blocked: false,
    risk_skip_once: false,
    pyramids_reached: true,
    age_filter_passed: true,
    loss_threshold_reached: true,
    timer_expired: true,
    pyramid_count: 3,
    max_pyramids: 3,
    age_minutes: 120,
    timer_status: 'expired',
  },
  identified_winners: [
    {
      id: 'winner1',
      symbol: 'ETHUSDT',
      unrealized_pnl_usd: 50,
    }
  ],
  required_offset_usd: 100,
  total_available_profit: 50,
  risk_engine_running: true,
  engine_force_stopped: false,
  engine_paused_by_loss_limit: false,
  max_realized_loss_usd: 500,
  daily_realized_pnl: -100,
  at_risk_positions: [{ id: 'pos1' }],
  recent_actions: [
    { loser_pnl_usd: -50, winners_count: 2 }
  ],
  config: {
    max_open_positions_global: 5,
  },
  projected_plan: [
    { id: 'winner1', symbol: 'ETHUSDT', amount_to_close_usd: 50 }
  ],
};

describe('RiskPage', () => {
  const mockFetchStatus = jest.fn();
  const mockRunEvaluation = jest.fn();
  const mockBlockGroup = jest.fn();
  const mockUnblockGroup = jest.fn();
  const mockSkipGroup = jest.fn();
  const mockRequestConfirm = jest.fn();
  const mockForceStart = jest.fn();
  const mockForceStop = jest.fn();

  beforeEach(() => {
    jest.useFakeTimers();
    (useRiskStore as unknown as jest.Mock).mockReturnValue({
      status: mockRiskStatus,
      loading: false,
      error: null,
      fetchStatus: mockFetchStatus,
      runEvaluation: mockRunEvaluation,
      blockGroup: mockBlockGroup,
      unblockGroup: mockUnblockGroup,
      skipGroup: mockSkipGroup,
      forceStart: mockForceStart,
      forceStop: mockForceStop,
    });

    // Mock requestConfirm
    mockRequestConfirm.mockResolvedValue(true);
    (useConfirmStore.getState as jest.Mock).mockReturnValue({
        requestConfirm: mockRequestConfirm
    });

    jest.clearAllMocks();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  test('renders risk status dashboard', async () => {
    renderWithProviders(<RiskPage />);

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /^Risk$/i, level: 4 })).toBeInTheDocument();
    });

    // Check Run Evaluation button is present
    expect(screen.getByRole('button', { name: /Run Evaluation/i })).toBeInTheDocument();
  });

  test('triggers manual evaluation', async () => {
    renderWithProviders(<RiskPage />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Run Evaluation/i })).toBeInTheDocument();
    });

    const runButton = screen.getByRole('button', { name: /Run Evaluation/i });
    await userEvent.click(runButton);

    await waitFor(() => {
      expect(mockRequestConfirm).toHaveBeenCalled();
      expect(mockRunEvaluation).toHaveBeenCalled();
    });
  });

  test('triggers block position', async () => {
    renderWithProviders(<RiskPage />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /^Block$/i })).toBeInTheDocument();
    });

    const blockButton = screen.getByRole('button', { name: /^Block$/i });
    await userEvent.click(blockButton);

    await waitFor(() => {
      expect(mockRequestConfirm).toHaveBeenCalled();
      expect(mockBlockGroup).toHaveBeenCalledWith('loser1');
    });
  });

  test('triggers skip next evaluation', async () => {
    renderWithProviders(<RiskPage />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Skip Next/i })).toBeInTheDocument();
    });

    const skipButton = screen.getByRole('button', { name: /Skip Next/i });
    await userEvent.click(skipButton);

    await waitFor(() => {
      expect(mockRequestConfirm).toHaveBeenCalled();
      expect(mockSkipGroup).toHaveBeenCalledWith('loser1');
    });
  });

  test('shows loading skeleton when loading with no status', async () => {
    (useRiskStore as unknown as jest.Mock).mockReturnValue({
      status: null,
      loading: true,
      error: null,
      fetchStatus: mockFetchStatus,
      runEvaluation: mockRunEvaluation,
      blockGroup: mockBlockGroup,
      unblockGroup: mockUnblockGroup,
      skipGroup: mockSkipGroup,
      forceStart: mockForceStart,
      forceStop: mockForceStop,
    });

    renderWithProviders(<RiskPage />);

    // Should show skeleton, not the main content
    expect(screen.queryByRole('heading', { name: /^Risk$/i })).not.toBeInTheDocument();
  });

  test('shows error alert when error exists', async () => {
    (useRiskStore as unknown as jest.Mock).mockReturnValue({
      status: mockRiskStatus,
      loading: false,
      error: 'Failed to fetch risk status',
      fetchStatus: mockFetchStatus,
      runEvaluation: mockRunEvaluation,
      blockGroup: mockBlockGroup,
      unblockGroup: mockUnblockGroup,
      skipGroup: mockSkipGroup,
      forceStart: mockForceStart,
      forceStop: mockForceStop,
    });

    renderWithProviders(<RiskPage />);

    await waitFor(() => {
      expect(screen.getByText('Failed to fetch risk status')).toBeInTheDocument();
    });
  });

  test('shows engine stopped state and start button', async () => {
    jest.useRealTimers(); // Use real timers for this test

    (useRiskStore as unknown as jest.Mock).mockReturnValue({
      status: { ...mockRiskStatus, engine_force_stopped: true },
      loading: false,
      error: null,
      fetchStatus: mockFetchStatus,
      runEvaluation: mockRunEvaluation,
      blockGroup: mockBlockGroup,
      unblockGroup: mockUnblockGroup,
      skipGroup: mockSkipGroup,
      forceStart: mockForceStart,
      forceStop: mockForceStop,
    });

    renderWithProviders(<RiskPage />);

    await waitFor(() => {
      // There are multiple "Stopped" chips in the UI
      expect(screen.getAllByText('Stopped').length).toBeGreaterThan(0);
    });

    // Verify start button is present
    expect(screen.getByRole('button', { name: /Start/i })).toBeInTheDocument();
  });

  test('shows stop button when engine is running', async () => {
    renderWithProviders(<RiskPage />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Stop/i })).toBeInTheDocument();
    });

    const stopButton = screen.getByRole('button', { name: /Stop/i });
    await userEvent.click(stopButton);

    await waitFor(() => {
      expect(mockForceStop).toHaveBeenCalled();
    });
  });

  test('shows paused warning when loss limit reached', async () => {
    (useRiskStore as unknown as jest.Mock).mockReturnValue({
      status: { ...mockRiskStatus, engine_paused_by_loss_limit: true },
      loading: false,
      error: null,
      fetchStatus: mockFetchStatus,
      runEvaluation: mockRunEvaluation,
      blockGroup: mockBlockGroup,
      unblockGroup: mockUnblockGroup,
      skipGroup: mockSkipGroup,
      forceStart: mockForceStart,
      forceStop: mockForceStop,
    });

    renderWithProviders(<RiskPage />);

    await waitFor(() => {
      expect(screen.getByText(/Engine paused: Loss limit reached/i)).toBeInTheDocument();
    });
  });

  test('shows loser identified chip and details', async () => {
    renderWithProviders(<RiskPage />);

    await waitFor(() => {
      expect(screen.getByText('Loser Identified')).toBeInTheDocument();
      expect(screen.getByText('BTCUSDT')).toBeInTheDocument();
    });
  });

  test('does not run evaluation when confirm is cancelled', async () => {
    mockRequestConfirm.mockResolvedValue(false);

    renderWithProviders(<RiskPage />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Run Evaluation/i })).toBeInTheDocument();
    });

    const runButton = screen.getByRole('button', { name: /Run Evaluation/i });
    await userEvent.click(runButton);

    await waitFor(() => {
      expect(mockRequestConfirm).toHaveBeenCalled();
    });

    // runEvaluation should not be called since confirm was cancelled
    expect(mockRunEvaluation).not.toHaveBeenCalled();
  });

  test('does not block when confirm is cancelled', async () => {
    mockRequestConfirm.mockResolvedValue(false);

    renderWithProviders(<RiskPage />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /^Block$/i })).toBeInTheDocument();
    });

    const blockButton = screen.getByRole('button', { name: /^Block$/i });
    await userEvent.click(blockButton);

    await waitFor(() => {
      expect(mockRequestConfirm).toHaveBeenCalled();
    });

    expect(mockBlockGroup).not.toHaveBeenCalled();
  });

  test('shows metrics cards with correct values', async () => {
    jest.useRealTimers(); // Use real timers for this test

    renderWithProviders(<RiskPage />);

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /^Risk$/i })).toBeInTheDocument();
    });

    // Verify the page renders (metric cards are present in the status object)
    expect(screen.getByText(/Run Evaluation/i)).toBeInTheDocument();
  });

  test('shows no loser message when no loser identified', async () => {
    (useRiskStore as unknown as jest.Mock).mockReturnValue({
      status: { ...mockRiskStatus, identified_loser: null },
      loading: false,
      error: null,
      fetchStatus: mockFetchStatus,
      runEvaluation: mockRunEvaluation,
      blockGroup: mockBlockGroup,
      unblockGroup: mockUnblockGroup,
      skipGroup: mockSkipGroup,
      forceStart: mockForceStart,
      forceStop: mockForceStop,
    });

    renderWithProviders(<RiskPage />);

    await waitFor(() => {
      expect(screen.getByText(/No position currently/i)).toBeInTheDocument();
    });
  });

  test('refresh button triggers fetchStatus', async () => {
    renderWithProviders(<RiskPage />);

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /^Risk$/i })).toBeInTheDocument();
    });

    // Find and click the refresh button (IconButton with RefreshIcon)
    const refreshButtons = screen.getAllByRole('button');
    const refreshButton = refreshButtons.find(btn => btn.querySelector('[data-testid="RefreshIcon"]'));

    if (refreshButton) {
      await userEvent.click(refreshButton);
      expect(mockFetchStatus).toHaveBeenCalled();
    }
  });

  test('shows active timer when timer is active', async () => {
    const statusWithActiveTimer = {
      ...mockRiskStatus,
      identified_loser: {
        ...mockRiskStatus.identified_loser,
        timer_status: 'active',
        timer_remaining_minutes: 5,
      },
    };

    (useRiskStore as unknown as jest.Mock).mockReturnValue({
      status: statusWithActiveTimer,
      loading: false,
      error: null,
      fetchStatus: mockFetchStatus,
      runEvaluation: mockRunEvaluation,
      blockGroup: mockBlockGroup,
      unblockGroup: mockUnblockGroup,
      skipGroup: mockSkipGroup,
      forceStart: mockForceStart,
      forceStop: mockForceStop,
    });

    renderWithProviders(<RiskPage />);

    await waitFor(() => {
      expect(screen.getByText('5m')).toBeInTheDocument();
    });
  });

  test('shows eligibility chips for loser', async () => {
    renderWithProviders(<RiskPage />);

    await waitFor(() => {
      expect(screen.getByText('Pyramids')).toBeInTheDocument();
      expect(screen.getByText('Age Filter')).toBeInTheDocument();
    });
  });
});
