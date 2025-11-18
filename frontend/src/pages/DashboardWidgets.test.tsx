import React from 'react';
import { render, screen } from '@testing-library/react';
import PoolUsageWidget from './PoolUsageWidget';
import SystemStatusWidget from './SystemStatusWidget';
import PnlCard from './PnlCard';
import { useDataStore } from '../store/dataStore';
import { useSystemStore } from '../store/systemStore';

jest.mock('../store/dataStore');
jest.mock('../store/systemStore');

describe('Dashboard Widgets', () => {
  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('PoolUsageWidget', () => {
    it('renders the pool usage data', () => {
      (useDataStore as jest.Mock).mockReturnValue({
        poolUsage: { active: 5, max: 10 },
      });
      render(<PoolUsageWidget />);
      expect(screen.getByText(/pool usage/i)).toBeInTheDocument();
      expect(screen.getByText(/5 \/ 10/i)).toBeInTheDocument();
    });
  });

  describe('SystemStatusWidget', () => {
    it('renders the system status data', () => {
      (useSystemStore as jest.Mock).mockReturnValue({
        engineStatus: 'Running',
        riskEngineStatus: 'Monitoring',
        lastWebhookTimestamp: '2025-11-18T12:00:00Z',
      });
      render(<SystemStatusWidget />);
      expect(screen.getByText(/system status/i)).toBeInTheDocument();
      expect(screen.getByText(/engine: running/i)).toBeInTheDocument();
      expect(screen.getByText(/risk engine: monitoring/i)).toBeInTheDocument();
      expect(screen.getByText(/last signal: 2025-11-18t12:00:00z/i)).toBeInTheDocument();
    });
  });

  describe('PnlCard', () => {
    it('renders the PnL data', () => {
      (useDataStore as jest.Mock).mockReturnValue({
        pnlMetrics: {
          unrealized_pnl: 123.45,
          realized_pnl: -67.89,
          total_pnl: 55.56,
        },
      });
      render(<PnlCard />);
      expect(screen.getByText(/unrealized pnl: \$123\.45/i)).toBeInTheDocument();
      expect(screen.getByText(/realized pnl: \$-67\.89/i)).toBeInTheDocument();
      expect(screen.getByText(/total pnl: \$55\.56/i)).toBeInTheDocument();
    });
  });
});