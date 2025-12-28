import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
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

// Helper to render with router
const renderWithRouter = (component: React.ReactElement) => {
  return render(<MemoryRouter>{component}</MemoryRouter>);
};

const mockUseQueueStore = useQueueStore as unknown as jest.Mock;

describe('QueuePage', () => {
  const mockFetchQueuedSignals = jest.fn();
  const mockPromoteSignal = jest.fn();
  const mockRemoveSignal = jest.fn();
  const mockRequestConfirm = jest.fn();

  beforeEach(() => {
    mockUseQueueStore.mockReturnValue({
      queuedSignals: [
        {
          id: '1',
          symbol: 'BTC/USD',
          side: 'buy',
          signal_type: 'grid_entry',
          priority_score: 10,
          created_at: '2023-01-01T10:00:00Z',
        },
        {
          id: '2',
          symbol: 'ETH/USD',
          side: 'sell',
          signal_type: 'dca_leg',
          priority_score: 5,
          created_at: '2023-01-02T10:00:00Z',
        },
      ],
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
    const removeButtons = screen.getAllByRole('button', { name: /remove/i });
    fireEvent.click(removeButtons[0]);

    await waitFor(() => {
        expect(mockRequestConfirm).toHaveBeenCalled();
        expect(mockRemoveSignal).toHaveBeenCalledWith('1');
    });
  });
});