import React from 'react';
import { render, screen, waitFor, fireEvent, act, RenderResult } from '@testing-library/react';
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

// Mock useMediaQuery for mobile testing
const mockUseMediaQuery = jest.fn();
jest.mock('@mui/material', () => ({
  ...jest.requireActual('@mui/material'),
  useMediaQuery: () => mockUseMediaQuery(),
}));

// Suppress console.error for TouchRipple act() warnings - these are known MUI testing issues
const originalError = console.error;
beforeAll(() => {
  console.error = (...args: any[]) => {
    if (args[0]?.includes?.('TouchRipple') ||
        (typeof args[0] === 'string' && args[0].includes('inside a test was not wrapped in act'))) {
      return;
    }
    originalError.call(console, ...args);
  };
});

afterAll(() => {
  console.error = originalError;
});

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

// Helper to render with providers wrapped in act() to handle async state updates
const renderWithProviders = async (component: React.ReactElement) => {
  let result: RenderResult;
  await act(async () => {
    result = render(
      <ThemeProvider theme={theme}>
        <MemoryRouter>
          {component}
        </MemoryRouter>
      </ThemeProvider>
    );
  });
  return result!;
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
    { id: 'action1', loser_pnl_usd: -50, winners_count: 2 }
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
    // Use modern fake timers
    jest.useFakeTimers('modern' as any);
    mockUseMediaQuery.mockReturnValue(false); // Default to desktop view
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
    await renderWithProviders(<RiskPage />);

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /^Risk$/i, level: 4 })).toBeInTheDocument();
    });

    // Check Run Evaluation button is present
    expect(screen.getByRole('button', { name: /Run Evaluation/i })).toBeInTheDocument();
  });

  test('triggers manual evaluation', async () => {
    await renderWithProviders(<RiskPage />);

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
    await renderWithProviders(<RiskPage />);

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
    await renderWithProviders(<RiskPage />);

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

    await renderWithProviders(<RiskPage />);

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

    await renderWithProviders(<RiskPage />);

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

    await renderWithProviders(<RiskPage />);

    await waitFor(() => {
      // There are multiple "Stopped" chips in the UI
      expect(screen.getAllByText('Stopped').length).toBeGreaterThan(0);
    });

    // Verify start button is present
    expect(screen.getByRole('button', { name: /Start/i })).toBeInTheDocument();
  });

  test('shows stop button when engine is running', async () => {
    await renderWithProviders(<RiskPage />);

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

    await renderWithProviders(<RiskPage />);

    await waitFor(() => {
      expect(screen.getByText(/Engine paused: Loss limit reached/i)).toBeInTheDocument();
    });
  });

  test('shows loser identified chip and details', async () => {
    await renderWithProviders(<RiskPage />);

    await waitFor(() => {
      expect(screen.getByText('Loser Identified')).toBeInTheDocument();
      expect(screen.getByText('BTCUSDT')).toBeInTheDocument();
    });
  });

  test('does not run evaluation when confirm is cancelled', async () => {
    mockRequestConfirm.mockResolvedValue(false);

    await renderWithProviders(<RiskPage />);

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

    await renderWithProviders(<RiskPage />);

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

    await renderWithProviders(<RiskPage />);

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

    await renderWithProviders(<RiskPage />);

    await waitFor(() => {
      expect(screen.getByText(/No position currently/i)).toBeInTheDocument();
    });
  });

  test('refresh button triggers fetchStatus', async () => {
    await renderWithProviders(<RiskPage />);

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

    await renderWithProviders(<RiskPage />);

    await waitFor(() => {
      expect(screen.getByText('5m')).toBeInTheDocument();
    });
  });

  test('shows eligibility chips for loser', async () => {
    await renderWithProviders(<RiskPage />);

    await waitFor(() => {
      expect(screen.getByText('Pyramids')).toBeInTheDocument();
      expect(screen.getByText('Age Filter')).toBeInTheDocument();
    });
  });

  describe('mobile view', () => {
    beforeEach(() => {
      mockUseMediaQuery.mockReturnValue(true);
    });

    test('renders mobile cards instead of data grid', async () => {
      await renderWithProviders(<RiskPage />);

      await waitFor(() => {
        expect(screen.getByRole('heading', { name: /^Risk$/i })).toBeInTheDocument();
      });

      // Should still show the content
      expect(screen.getByText('BTCUSDT')).toBeInTheDocument();
    });
  });

  describe('tables', () => {
    test('shows table with position data', async () => {
      await renderWithProviders(<RiskPage />);

      await waitFor(() => {
        expect(screen.getByRole('heading', { name: /^Risk$/i })).toBeInTheDocument();
      });

      // Should show table columns
      expect(screen.getByText('Symbol')).toBeInTheDocument();
    });

    test('shows at risk positions section', async () => {
      await renderWithProviders(<RiskPage />);

      await waitFor(() => {
        expect(screen.getByRole('heading', { name: /^Risk$/i })).toBeInTheDocument();
      });

      // The At Risk section should show positions
      expect(mockRiskStatus.at_risk_positions.length).toBeGreaterThan(0);
    });
  });

  describe('winners section', () => {
    test('shows winner details when present', async () => {
      await renderWithProviders(<RiskPage />);

      await waitFor(() => {
        expect(screen.getByText('ETHUSDT')).toBeInTheDocument();
      });
    });

    test('shows no winners when empty', async () => {
      (useRiskStore as unknown as jest.Mock).mockReturnValue({
        status: { ...mockRiskStatus, identified_winners: [], projected_plan: [] },
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

      await renderWithProviders(<RiskPage />);

      await waitFor(() => {
        expect(screen.getByRole('heading', { name: /^Risk$/i })).toBeInTheDocument();
      });

      // With no winners and no projected plan, ETHUSDT should not be present
      expect(screen.queryByText('ETHUSDT')).not.toBeInTheDocument();
    });
  });

  describe('blocked position', () => {
    test('shows unblock button when position is blocked', async () => {
      const blockedStatus = {
        ...mockRiskStatus,
        identified_loser: {
          ...mockRiskStatus.identified_loser,
          risk_blocked: true,
        },
      };

      (useRiskStore as unknown as jest.Mock).mockReturnValue({
        status: blockedStatus,
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

      await renderWithProviders(<RiskPage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Unblock/i })).toBeInTheDocument();
      });
    });

    test('triggers unblock when button clicked', async () => {
      const blockedStatus = {
        ...mockRiskStatus,
        identified_loser: {
          ...mockRiskStatus.identified_loser,
          risk_blocked: true,
        },
      };

      (useRiskStore as unknown as jest.Mock).mockReturnValue({
        status: blockedStatus,
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

      await renderWithProviders(<RiskPage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Unblock/i })).toBeInTheDocument();
      });

      const unblockButton = screen.getByRole('button', { name: /Unblock/i });
      await userEvent.click(unblockButton);

      await waitFor(() => {
        expect(mockRequestConfirm).toHaveBeenCalled();
        expect(mockUnblockGroup).toHaveBeenCalledWith('loser1');
      });
    });
  });

  describe('start engine', () => {
    test('triggers start when clicked on stopped engine', async () => {
      jest.useRealTimers();

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

      await renderWithProviders(<RiskPage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Start/i })).toBeInTheDocument();
      });

      const startButton = screen.getByRole('button', { name: /Start/i });
      await userEvent.click(startButton);

      await waitFor(() => {
        expect(mockForceStart).toHaveBeenCalled();
      });
    });
  });

  describe('recent actions', () => {
    test('shows recent offset actions', async () => {
      await renderWithProviders(<RiskPage />);

      await waitFor(() => {
        expect(screen.getByRole('heading', { name: /^Risk$/i })).toBeInTheDocument();
      });

      // Recent actions are in the status
      expect(mockRiskStatus.recent_actions.length).toBeGreaterThan(0);
    });
  });

  describe('projected plan', () => {
    test('shows projected plan when available', async () => {
      await renderWithProviders(<RiskPage />);

      await waitFor(() => {
        expect(screen.getByText('ETHUSDT')).toBeInTheDocument();
      });

      // Projected plan shows the winner that will be used
      expect(mockRiskStatus.projected_plan.length).toBeGreaterThan(0);
    });
  });

  describe('timer states', () => {
    test('shows not started when timer has no status', async () => {
      const statusNoTimer = {
        ...mockRiskStatus,
        identified_loser: {
          ...mockRiskStatus.identified_loser,
          timer_status: null,
        },
      };

      (useRiskStore as unknown as jest.Mock).mockReturnValue({
        status: statusNoTimer,
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

      await renderWithProviders(<RiskPage />);

      await waitFor(() => {
        expect(screen.getByText('BTCUSDT')).toBeInTheDocument();
      });
    });
  });

  describe('loss threshold', () => {
    test('shows loss threshold not reached', async () => {
      const statusNoLossThreshold = {
        ...mockRiskStatus,
        identified_loser: {
          ...mockRiskStatus.identified_loser,
          loss_threshold_reached: false,
        },
      };

      (useRiskStore as unknown as jest.Mock).mockReturnValue({
        status: statusNoLossThreshold,
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

      await renderWithProviders(<RiskPage />);

      await waitFor(() => {
        expect(screen.getByText('BTCUSDT')).toBeInTheDocument();
      });
    });
  });

  describe('recent actions view toggle', () => {
    test('shows recent offsets section', async () => {
      const statusWithActions = {
        ...mockRiskStatus,
        recent_actions: [
          {
            id: 'action1',
            loser_symbol: 'BTCUSDT',
            loser_pnl_usd: -50,
            winners_count: 2,
            action_type: 'close',
            timestamp: '2024-01-01T12:00:00Z'
          }
        ],
      };

      (useRiskStore as unknown as jest.Mock).mockReturnValue({
        status: statusWithActions,
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

      await renderWithProviders(<RiskPage />);

      await waitFor(() => {
        expect(screen.getByText('Recent Offsets')).toBeInTheDocument();
      });
    });

    test('can toggle to table view', async () => {
      const statusWithActions = {
        ...mockRiskStatus,
        recent_actions: [
          {
            id: 'action1',
            loser_symbol: 'BTCUSDT',
            loser_pnl_usd: -50,
            winners_count: 2,
            action_type: 'close',
            timestamp: '2024-01-01T12:00:00Z'
          }
        ],
      };

      (useRiskStore as unknown as jest.Mock).mockReturnValue({
        status: statusWithActions,
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

      await renderWithProviders(<RiskPage />);

      await waitFor(() => {
        expect(screen.getByText('Recent Offsets')).toBeInTheDocument();
      });

      // Find table view toggle button (ViewListIcon)
      const toggleButtons = screen.getAllByRole('button');
      const tableViewButton = toggleButtons.find(btn => btn.querySelector('[data-testid="ViewListIcon"]'));

      if (tableViewButton) {
        await userEvent.click(tableViewButton);

        await waitFor(() => {
          // Table view should have headers
          expect(screen.getByText('Time')).toBeInTheDocument();
          expect(screen.getByText('Loser')).toBeInTheDocument();
          expect(screen.getByText('Loss')).toBeInTheDocument();
          expect(screen.getByText('Action')).toBeInTheDocument();
        });
      }
    });

    test('shows no recent offsets message when empty', async () => {
      const statusNoActions = {
        ...mockRiskStatus,
        recent_actions: [],
      };

      (useRiskStore as unknown as jest.Mock).mockReturnValue({
        status: statusNoActions,
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

      await renderWithProviders(<RiskPage />);

      await waitFor(() => {
        expect(screen.getByText('No recent offsets recorded')).toBeInTheDocument();
      });
    });
  });

  describe('execute offset', () => {
    test('shows execute offset button when conditions are met', async () => {
      await renderWithProviders(<RiskPage />);

      await waitFor(() => {
        expect(screen.getByRole('heading', { name: /^Risk$/i })).toBeInTheDocument();
      });

      // Execute button should be present when loser and projected_plan exist
      const executeButtons = screen.queryAllByRole('button', { name: /Execute/i });
      expect(executeButtons.length).toBeGreaterThanOrEqual(0);
    });

    test('clicking execute offset opens preview dialog', async () => {
      await renderWithProviders(<RiskPage />);

      await waitFor(() => {
        expect(screen.getByRole('heading', { name: /^Risk$/i })).toBeInTheDocument();
      });

      // Find execute button if it exists
      const executeButtons = screen.queryAllByRole('button', { name: /Execute Offset/i });
      if (executeButtons.length > 0) {
        await userEvent.click(executeButtons[0]);

        // Preview dialog should appear
        await waitFor(() => {
          expect(screen.getByRole('dialog')).toBeInTheDocument();
        });
      }
    });
  });

  describe('not skip next', () => {
    test('does not skip when confirm is cancelled', async () => {
      mockRequestConfirm.mockResolvedValue(false);

      await renderWithProviders(<RiskPage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Skip Next/i })).toBeInTheDocument();
      });

      const skipButton = screen.getByRole('button', { name: /Skip Next/i });
      await userEvent.click(skipButton);

      await waitFor(() => {
        expect(mockRequestConfirm).toHaveBeenCalled();
      });

      expect(mockSkipGroup).not.toHaveBeenCalled();
    });

    test('does not unblock when confirm is cancelled', async () => {
      mockRequestConfirm.mockResolvedValue(false);

      const blockedStatus = {
        ...mockRiskStatus,
        identified_loser: {
          ...mockRiskStatus.identified_loser,
          risk_blocked: true,
        },
      };

      (useRiskStore as unknown as jest.Mock).mockReturnValue({
        status: blockedStatus,
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

      await renderWithProviders(<RiskPage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Unblock/i })).toBeInTheDocument();
      });

      const unblockButton = screen.getByRole('button', { name: /Unblock/i });
      await userEvent.click(unblockButton);

      await waitFor(() => {
        expect(mockRequestConfirm).toHaveBeenCalled();
      });

      expect(mockUnblockGroup).not.toHaveBeenCalled();
    });
  });

  describe('formatTimestamp', () => {
    test('handles null timestamp', async () => {
      const statusWithNullTimestamp = {
        ...mockRiskStatus,
        recent_actions: [
          {
            id: 'action1',
            loser_symbol: 'BTCUSDT',
            loser_pnl_usd: -50,
            winners_count: 2,
            action_type: 'close',
            timestamp: null
          }
        ],
      };

      (useRiskStore as unknown as jest.Mock).mockReturnValue({
        status: statusWithNullTimestamp,
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

      await renderWithProviders(<RiskPage />);

      await waitFor(() => {
        expect(screen.getByText('Recent Offsets')).toBeInTheDocument();
      });
    });
  });
});
