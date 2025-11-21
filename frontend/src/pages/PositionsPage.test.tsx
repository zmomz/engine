import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import PositionsPage from './PositionsPage';
import axios from 'axios';

jest.mock('axios');
const mockedAxios = axios as jest.Mocked<typeof axios>;

// Mock auth store to avoid issues if it's used
jest.mock('../store/authStore', () => ({
  __esModule: true,
  default: (selector: any) => selector({ user: { id: '1' } }),
}));

describe('PositionsPage', () => {
  const mockPositions = [
    {
      id: '1',
      symbol: 'BTC/USD',
      side: 'long',
      status: 'active',
      pnl: 500,
      pyramids: [],
    },
    {
      id: '2',
      symbol: 'ETH/USD',
      side: 'short',
      status: 'closing',
      pnl: -100,
      pyramids: [],
    },
  ];

  beforeEach(() => {
    mockedAxios.get.mockResolvedValue({ data: mockPositions });
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  it('renders the positions table with data', async () => {
    render(<PositionsPage />);
    
    expect(screen.getByText(/positions/i)).toBeInTheDocument();

    // Wait for data to be loaded
    await waitFor(() => {
      expect(screen.getByText('BTC/USD')).toBeInTheDocument();
    });

    expect(screen.getByText('ETH/USD')).toBeInTheDocument();
    expect(screen.getByText('long')).toBeInTheDocument();
    expect(screen.getByText('short')).toBeInTheDocument();
    expect(screen.getByText('$500.00')).toBeInTheDocument();
    expect(screen.getByText('$-100.00')).toBeInTheDocument();
  });
});