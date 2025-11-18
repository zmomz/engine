import React from 'react';
import { render, screen, within } from '@testing-library/react';
import PositionsPage from './PositionsPage';
import { useDataStore } from '../store/dataStore';

jest.mock('../store/dataStore', () => ({
  useDataStore: jest.fn(),
}));

describe('PositionsPage', () => {
  beforeEach(() => {
    (useDataStore as jest.Mock).mockReturnValue({
      positionGroups: [
        {
          id: '1',
          symbol: 'BTC/USD',
          exchange: 'binance',
          direction: 'long',
          status: 'active',
          total_quantity: 0.1,
          avg_entry_price: 20000,
          unrealized_pnl_usd: 500,
          unrealized_pnl_percent: 2.5,
        },
        {
          id: '2',
          symbol: 'ETH/USD',
          exchange: 'bybit',
          direction: 'short',
          status: 'closed',
          total_quantity: 0.5,
          avg_entry_price: 1500,
          unrealized_pnl_usd: -100,
          unrealized_pnl_percent: -1.0,
        },
      ],
    });
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  it('renders the positions table with data', async () => {
    render(<PositionsPage />);
    expect(screen.getByRole('heading', { name: /positions/i })).toBeInTheDocument();

    // Use findByRole to wait for the grid to render
    const grid = await screen.findByRole('grid');

    // Check for BTC row and its contents
    const btcRow = within(grid).getByText(/btc\/usd/i).closest('div[role="row"]');
    expect(btcRow).not.toBeNull();
    if (btcRow) {
      expect(within(btcRow).getByText(/binance/i)).toBeInTheDocument();
      expect(within(btcRow).getByText(/long/i)).toBeInTheDocument();
      expect(within(btcRow).getByText(/active/i)).toBeInTheDocument();
      expect(within(btcRow).getByText('0.1')).toBeInTheDocument();
      expect(within(btcRow).getByText('20,000')).toBeInTheDocument();
      expect(within(btcRow).getByText('$500.00')).toBeInTheDocument();
      expect(within(btcRow).getByText('2.50%')).toBeInTheDocument();
    }


    // Check for ETH row and its contents
    const ethRow = within(grid).getByText(/eth\/usd/i).closest('div[role="row"]');
    expect(ethRow).not.toBeNull();
    if (ethRow) {
      expect(within(ethRow).getByText(/bybit/i)).toBeInTheDocument();
      expect(within(ethRow).getByText(/short/i)).toBeInTheDocument();
      expect(within(ethRow).getByText(/closed/i)).toBeInTheDocument();
      expect(within(ethRow).getByText('0.5')).toBeInTheDocument();
      expect(within(ethRow).getByText('1,500')).toBeInTheDocument();
      expect(within(ethRow).getByText('$-100.00')).toBeInTheDocument();
      expect(within(ethRow).getByText('-1.00%')).toBeInTheDocument();
    }
  });
});