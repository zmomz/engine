import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import QueuePage from './QueuePage';
import { useDataStore } from '../store/dataStore';

jest.mock('../store/dataStore', () => ({
  useDataStore: jest.fn(),
}));

describe('QueuePage', () => {
  beforeEach(() => {
    (useDataStore as jest.Mock).mockReturnValue({
      queuedSignals: [
        {
          id: '1',
          symbol: 'BTC/USD',
          exchange: 'binance',
          direction: 'long',
          status: 'pending',
          created_at: '2023-01-01T10:00:00Z',
        },
        {
          id: '2',
          symbol: 'ETH/USD',
          exchange: 'bybit',
          direction: 'short',
          status: 'pending',
          created_at: '2023-01-02T10:00:00Z',
        },
      ],
    });
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  it('renders the queue table with data', () => {
    render(<QueuePage />);
    expect(screen.getByText(/queued signals/i)).toBeInTheDocument();
    expect(screen.getByText(/btc\/usd/i)).toBeInTheDocument();
    expect(screen.getByText(/eth\/usd/i)).toBeInTheDocument();
    expect(screen.getByText(/binance/i)).toBeInTheDocument();
    expect(screen.getByText(/bybit/i)).toBeInTheDocument();
    expect(screen.getAllByText(/pending/i).length).toBe(2);
  });

  it('renders action buttons for each row', () => {
    render(<QueuePage />);
    const promoteButtons = screen.getAllByRole('button', { name: /promote/i });
    const forceAddButtons = screen.getAllByRole('button', { name: /force add/i });

    expect(promoteButtons.length).toBe(2);
    expect(forceAddButtons.length).toBe(2);
  });

  it('opens a confirmation modal when "Force Add" is clicked', () => {
    render(<QueuePage />);
    const forceAddButtons = screen.getAllByRole('button', { name: /force add/i });
    fireEvent.click(forceAddButtons[0]);

    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByText(/confirm force add/i)).toBeInTheDocument();
  });
});
