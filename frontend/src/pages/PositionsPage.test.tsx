import React from 'react';
import { render, screen, within } from '@testing-library/react';
import PositionsPage from './PositionsPage';
import { useDataStore } from '../store/dataStore';

jest.mock('../store/dataStore', () => ({
  useDataStore: jest.fn(),
}));

describe('PositionsPage', () => {
  beforeEach(() => {
    (useDataStore as any).mockReturnValue({
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
      const btcRowWithin = within(btcRow as HTMLElement);
      expect(btcRowWithin.getByText(/binance/i)).toBeInTheDocument();
      expect(btcRowWithin.getByText(/long/i)).toBeInTheDocument();
      expect(btcRowWithin.getByText(/active/i)).toBeInTheDocument();
      expect(btcRowWithin.getByText('0.1')).toBeInTheDocument();
      expect(btcRowWithin.getByText('20,000')).toBeInTheDocument();
      expect(btcRowWithin.getByText('$500.00')).toBeInTheDocument();
      expect(btcRowWithin.getByText('2.50%')).toBeInTheDocument();
    }


    // Check for ETH row and its contents
    const ethRow = within(grid).getByText(/eth\/usd/i).closest('div[role="row"]');
    expect(ethRow).not.toBeNull();
    if (ethRow) {
      const ethRowWithin = within(ethRow as HTMLElement);
      expect(ethRowWithin.getByText(/bybit/i)).toBeInTheDocument();
      expect(ethRowWithin.getByText(/short/i)).toBeInTheDocument();
      expect(ethRowWithin.getByText(/closed/i)).toBeInTheDocument();
      expect(ethRowWithin.getByText('0.5')).toBeInTheDocument();
      expect(ethRowWithin.getByText('1,500')).toBeInTheDocument();
      expect(ethRowWithin.getByText('$-100.00')).toBeInTheDocument();
      expect(ethRowWithin.getByText('-1.00%')).toBeInTheDocument();
    }
  });
});
