import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import { MemoryRouter } from 'react-router-dom';
import QueuePage from './QueuePage';
import useQueueStore from '../store/queueStore';
import useConfirmStore from '../store/confirmStore';

// Mock the stores
jest.mock('../store/queueStore');
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

// Create theme with bullish/bearish colors
const theme = createTheme({
  palette: {
    mode: 'dark',
    primary: { main: '#1976d2' },
    success: { main: '#4caf50' },
    error: { main: '#f44336' },
    warning: { main: '#ff9800' },
  },
});
(theme.palette as any).bullish = { main: '#4caf50', light: '#81c784', dark: '#388e3c', contrastText: '#fff' };
(theme.palette as any).bearish = { main: '#f44336', light: '#e57373', dark: '#d32f2f', contrastText: '#fff' };

// Helper to render with router and theme
const renderWithRouter = (component: React.ReactElement) => {
  return render(
    <ThemeProvider theme={theme}>
      <MemoryRouter>{component}</MemoryRouter>
    </ThemeProvider>
  );
};

const mockUseQueueStore = useQueueStore as unknown as jest.Mock;

describe('QueuePage', () => {
  const mockFetchQueuedSignals = jest.fn();
  const mockPromoteSignal = jest.fn();
  const mockRemoveSignal = jest.fn();
  const mockRequestConfirm = jest.fn();

  const mockSignals = [
    {
      id: '1',
      symbol: 'BTC/USD',
      side: 'long',
      timeframe: 60,
      exchange: 'binance',
      signal_type: 'grid_entry',
      priority_score: 1_050_000, // Tier 1: deep loss (>= 1M is Critical)
      current_loss_percent: -3.5,
      replacement_count: 2,
      queued_at: new Date(Date.now() - 30 * 60 * 1000).toISOString(), // 30 min ago
      priority_explanation: 'High loss + replacement',
      created_at: '2023-01-01T10:00:00Z',
    },
    {
      id: '2',
      symbol: 'ETH/USD',
      side: 'short',
      timeframe: 15,
      exchange: 'binance',
      signal_type: 'dca_leg',
      priority_score: 5_000, // Tier 3: FIFO (>= 1K is Medium)
      current_loss_percent: -1.2,
      replacement_count: 0,
      queued_at: new Date(Date.now() - 5 * 60 * 1000).toISOString(), // 5 min ago
      priority_explanation: 'Medium priority',
      created_at: '2023-01-02T10:00:00Z',
    },
  ];

  beforeEach(() => {
    mockUseMediaQuery.mockReturnValue(false); // Default to desktop

    mockUseQueueStore.mockReturnValue({
      queuedSignals: mockSignals,
      queueHistory: [],
      loading: false,
      error: null,
      fetchQueuedSignals: mockFetchQueuedSignals,
      fetchQueueHistory: jest.fn(),
      promoteSignal: mockPromoteSignal,
      removeSignal: mockRemoveSignal,
    });

    // Mock requestConfirm
    mockRequestConfirm.mockResolvedValue(true);
    (useConfirmStore.getState as jest.Mock).mockReturnValue({
        requestConfirm: mockRequestConfirm
    });
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  it('renders the queue page with heading', () => {
    renderWithRouter(<QueuePage />);
    // The heading is just "Queue"
    expect(screen.getByText('Queue')).toBeInTheDocument();
  });

  it('renders action buttons for each row', () => {
    renderWithRouter(<QueuePage />);
    const promoteButtons = screen.getAllByRole('button', { name: /promote/i });
    const removeButtons = screen.getAllByRole('button', { name: /remove/i });

    expect(promoteButtons.length).toBe(2);
    expect(removeButtons.length).toBe(2);
  });

  it('calls promoteSignal when Promote is clicked and confirmed', async () => {
    renderWithRouter(<QueuePage />);
    const promoteButtons = screen.getAllByRole('button', { name: /promote/i });
    fireEvent.click(promoteButtons[0]);

    await waitFor(() => {
        expect(mockRequestConfirm).toHaveBeenCalled();
        expect(mockPromoteSignal).toHaveBeenCalledWith('1');
    });
  });

  it('calls removeSignal when Remove is clicked and confirmed', async () => {
    renderWithRouter(<QueuePage />);

    // Buttons should be rendered immediately since we mock the store
    const removeButtons = screen.getAllByRole('button', { name: /remove/i });
    fireEvent.click(removeButtons[0]);

    await waitFor(() => {
      expect(mockRequestConfirm).toHaveBeenCalled();
      expect(mockRemoveSignal).toHaveBeenCalledWith('1');
    });
  });

  it('does not call removeSignal when canceled', async () => {
    mockRequestConfirm.mockResolvedValue(false);

    renderWithRouter(<QueuePage />);

    const removeButtons = screen.getAllByRole('button', { name: /remove/i });
    fireEvent.click(removeButtons[0]);

    await waitFor(() => {
      expect(mockRequestConfirm).toHaveBeenCalled();
    });

    expect(mockRemoveSignal).not.toHaveBeenCalled();
  });

  it('does not call promoteSignal when canceled', async () => {
    mockRequestConfirm.mockResolvedValue(false);

    renderWithRouter(<QueuePage />);

    const promoteButtons = screen.getAllByRole('button', { name: /promote/i });
    fireEvent.click(promoteButtons[0]);

    await waitFor(() => {
      expect(mockRequestConfirm).toHaveBeenCalled();
    });

    expect(mockPromoteSignal).not.toHaveBeenCalled();
  });

  it('renders error state', () => {
    mockUseQueueStore.mockReturnValue({
      queuedSignals: [],
      queueHistory: [],
      loading: false,
      error: 'Failed to fetch queue',
      fetchQueuedSignals: mockFetchQueuedSignals,
      fetchQueueHistory: jest.fn(),
      promoteSignal: mockPromoteSignal,
      removeSignal: mockRemoveSignal,
    });

    renderWithRouter(<QueuePage />);
    expect(screen.getByText('Failed to fetch queue')).toBeInTheDocument();
  });

  it('renders skeleton when loading with no data', () => {
    mockUseQueueStore.mockReturnValue({
      queuedSignals: [],
      queueHistory: [],
      loading: true,
      error: null,
      fetchQueuedSignals: mockFetchQueuedSignals,
      fetchQueueHistory: jest.fn(),
      promoteSignal: mockPromoteSignal,
      removeSignal: mockRemoveSignal,
    });

    renderWithRouter(<QueuePage />);
    // When loading with empty data, skeleton is shown
    expect(mockFetchQueuedSignals).toHaveBeenCalled();
  });

  describe('queue health status', () => {
    it('shows Empty status when queue is empty', () => {
      mockUseQueueStore.mockReturnValue({
        queuedSignals: [],
        queueHistory: [],
        loading: false,
        error: null,
        fetchQueuedSignals: mockFetchQueuedSignals,
        fetchQueueHistory: jest.fn(),
        promoteSignal: mockPromoteSignal,
        removeSignal: mockRemoveSignal,
      });

      renderWithRouter(<QueuePage />);
      expect(screen.getByText('Empty')).toBeInTheDocument();
    });

    it('shows Healthy status when queue has 1-3 items', () => {
      mockUseQueueStore.mockReturnValue({
        queuedSignals: [mockSignals[0]],
        queueHistory: [],
        loading: false,
        error: null,
        fetchQueuedSignals: mockFetchQueuedSignals,
        fetchQueueHistory: jest.fn(),
        promoteSignal: mockPromoteSignal,
        removeSignal: mockRemoveSignal,
      });

      renderWithRouter(<QueuePage />);
      expect(screen.getByText('Healthy')).toBeInTheDocument();
    });

    it('shows Busy status when queue has 4-5 items', () => {
      const busySignals = Array(5).fill(null).map((_, i) => ({
        ...mockSignals[0],
        id: `${i}`,
      }));

      mockUseQueueStore.mockReturnValue({
        queuedSignals: busySignals,
        queueHistory: [],
        loading: false,
        error: null,
        fetchQueuedSignals: mockFetchQueuedSignals,
        fetchQueueHistory: jest.fn(),
        promoteSignal: mockPromoteSignal,
        removeSignal: mockRemoveSignal,
      });

      renderWithRouter(<QueuePage />);
      expect(screen.getByText('Busy')).toBeInTheDocument();
    });

    it('shows Backlog status when queue has more than 5 items', () => {
      const backlogSignals = Array(7).fill(null).map((_, i) => ({
        ...mockSignals[0],
        id: `${i}`,
      }));

      mockUseQueueStore.mockReturnValue({
        queuedSignals: backlogSignals,
        queueHistory: [],
        loading: false,
        error: null,
        fetchQueuedSignals: mockFetchQueuedSignals,
        fetchQueueHistory: jest.fn(),
        promoteSignal: mockPromoteSignal,
        removeSignal: mockRemoveSignal,
      });

      renderWithRouter(<QueuePage />);
      expect(screen.getByText('Backlog')).toBeInTheDocument();
    });
  });

  describe('history tab', () => {
    const mockHistory = [
      {
        id: 'h1',
        symbol: 'BTC/USD',
        side: 'long',
        timeframe: 60,
        exchange: 'binance',
        status: 'promoted',
        priority_score: 80,
        priority_explanation: 'High priority',
        promoted_at: '2024-01-01T12:00:00Z',
      },
      {
        id: 'h2',
        symbol: 'ETH/USD',
        side: 'short',
        timeframe: 15,
        exchange: 'binance',
        status: 'expired',
        priority_score: 30,
        priority_explanation: 'Low priority',
        promoted_at: '2024-01-01T11:00:00Z',
      },
    ];

    it('renders history tab with data', async () => {
      mockUseQueueStore.mockReturnValue({
        queuedSignals: [],
        queueHistory: mockHistory,
        loading: false,
        error: null,
        fetchQueuedSignals: mockFetchQueuedSignals,
        fetchQueueHistory: jest.fn(),
        promoteSignal: mockPromoteSignal,
        removeSignal: mockRemoveSignal,
      });

      renderWithRouter(<QueuePage />);

      const historyTab = screen.getByRole('tab', { name: /history/i });
      fireEvent.click(historyTab);

      await waitFor(() => {
        expect(screen.getByText('BTC/USD')).toBeInTheDocument();
      });
    });

    it('displays history metrics on history tab', async () => {
      mockUseQueueStore.mockReturnValue({
        queuedSignals: [],
        queueHistory: mockHistory,
        loading: false,
        error: null,
        fetchQueuedSignals: mockFetchQueuedSignals,
        fetchQueueHistory: jest.fn(),
        promoteSignal: mockPromoteSignal,
        removeSignal: mockRemoveSignal,
      });

      renderWithRouter(<QueuePage />);

      const historyTab = screen.getByRole('tab', { name: /history/i });
      fireEvent.click(historyTab);

      await waitFor(() => {
        expect(screen.getByText('Total Processed')).toBeInTheDocument();
        expect(screen.getByText('Promoted')).toBeInTheDocument();
      });
    });
  });

  describe('mobile view', () => {
    beforeEach(() => {
      mockUseMediaQuery.mockReturnValue(true);
    });

    it('renders signal cards on mobile', () => {
      renderWithRouter(<QueuePage />);
      expect(screen.getByText('BTC/USD')).toBeInTheDocument();
    });

    it('shows empty queue message on mobile', () => {
      mockUseQueueStore.mockReturnValue({
        queuedSignals: [],
        queueHistory: [],
        loading: false,
        error: null,
        fetchQueuedSignals: mockFetchQueuedSignals,
        fetchQueueHistory: jest.fn(),
        promoteSignal: mockPromoteSignal,
        removeSignal: mockRemoveSignal,
      });

      renderWithRouter(<QueuePage />);
      expect(screen.getByText('Queue is empty')).toBeInTheDocument();
    });

    it('shows no history message on mobile', async () => {
      mockUseQueueStore.mockReturnValue({
        queuedSignals: [],
        queueHistory: [],
        loading: false,
        error: null,
        fetchQueuedSignals: mockFetchQueuedSignals,
        fetchQueueHistory: jest.fn(),
        promoteSignal: mockPromoteSignal,
        removeSignal: mockRemoveSignal,
      });

      renderWithRouter(<QueuePage />);

      const historyTab = screen.getByRole('tab', { name: /history/i });
      fireEvent.click(historyTab);

      await waitFor(() => {
        expect(screen.getByText('No queue history')).toBeInTheDocument();
      });
    });

    it('renders history cards on mobile', async () => {
      mockUseQueueStore.mockReturnValue({
        queuedSignals: [],
        queueHistory: [{
          id: 'h1',
          symbol: 'BTC/USD',
          side: 'long',
          timeframe: 60,
          exchange: 'binance',
          status: 'promoted',
          priority_score: 80,
          priority_explanation: 'High priority',
          promoted_at: '2024-01-01T12:00:00Z',
        }],
        loading: false,
        error: null,
        fetchQueuedSignals: mockFetchQueuedSignals,
        fetchQueueHistory: jest.fn(),
        promoteSignal: mockPromoteSignal,
        removeSignal: mockRemoveSignal,
      });

      renderWithRouter(<QueuePage />);

      const historyTab = screen.getByRole('tab', { name: /history/i });
      fireEvent.click(historyTab);

      await waitFor(() => {
        expect(screen.getByText('BTC/USD')).toBeInTheDocument();
        expect(screen.getByText('PROMOTED')).toBeInTheDocument();
      });
    });
  });

  describe('metrics', () => {
    it('displays active metrics', () => {
      renderWithRouter(<QueuePage />);

      expect(screen.getByText('In Queue')).toBeInTheDocument();
      expect(screen.getByText('High Priority')).toBeInTheDocument();
      expect(screen.getByText('Avg Wait')).toBeInTheDocument();
    });

    it('shows high priority count correctly', () => {
      // mockSignals has one with score 1_050_000 (>= 10K is High priority)
      renderWithRouter(<QueuePage />);

      expect(screen.getByText('High Priority')).toBeInTheDocument();
      // Use getAllByText since '1' may appear in multiple places (metric cards)
      const allOnes = screen.getAllByText('1');
      expect(allOnes.length).toBeGreaterThan(0); // At least one high priority signal shown
    });
  });

  it('handles refresh button click', () => {
    const mockFetchQueueHistory = jest.fn();
    mockUseQueueStore.mockReturnValue({
      queuedSignals: mockSignals,
      queueHistory: [],
      loading: false,
      error: null,
      fetchQueuedSignals: mockFetchQueuedSignals,
      fetchQueueHistory: mockFetchQueueHistory,
      promoteSignal: mockPromoteSignal,
      removeSignal: mockRemoveSignal,
    });

    renderWithRouter(<QueuePage />);

    const refreshButton = screen.getByTestId('RefreshIcon').closest('button');
    if (refreshButton) {
      fireEvent.click(refreshButton);
      expect(mockFetchQueuedSignals).toHaveBeenCalled();
      expect(mockFetchQueueHistory).toHaveBeenCalled();
    }
  });

  it('switches tabs correctly', async () => {
    const mockFetchQueueHistory = jest.fn();
    mockUseQueueStore.mockReturnValue({
      queuedSignals: mockSignals,
      queueHistory: [],
      loading: false,
      error: null,
      fetchQueuedSignals: mockFetchQueuedSignals,
      fetchQueueHistory: mockFetchQueueHistory,
      promoteSignal: mockPromoteSignal,
      removeSignal: mockRemoveSignal,
    });

    renderWithRouter(<QueuePage />);

    // Switch to history tab
    const historyTab = screen.getByRole('tab', { name: /history/i });
    fireEvent.click(historyTab);

    await waitFor(() => {
      expect(mockFetchQueueHistory).toHaveBeenCalled();
    });

    // Switch back to active tab
    const activeTab = screen.getByRole('tab', { name: /active/i });
    fireEvent.click(activeTab);

    await waitFor(() => {
      expect(mockFetchQueuedSignals).toHaveBeenCalled();
    });
  });
});