import React from 'react';
import { render, screen } from '@testing-library/react';
import PoolUsageWidget from './PoolUsageWidget';
import SystemStatusWidget from './SystemStatusWidget';
import PnlCard from './PnlCard';
import EquityCurveChart from './EquityCurveChart';
import { useDataStore } from '../store/dataStore';
import { useSystemStore } from '../store/systemStore';

jest.mock('../store/dataStore', () => ({
  useDataStore: jest.fn(),
}));
jest.mock('../store/systemStore', () => ({
  useSystemStore: jest.fn(),
}));

describe('Dashboard Widgets', () => {
  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('PoolUsageWidget', () => {
    it('renders the pool usage data and a progress bar', () => {
      (useDataStore as jest.Mock).mockReturnValue({
        poolUsage: { active: 5, max: 10 },
      });
      render(<PoolUsageWidget />);
      expect(screen.getByText(/pool usage/i)).toBeInTheDocument();
      expect(screen.getByText(/5 \/ 10/i)).toBeInTheDocument();
      expect(screen.getByRole('progressbar')).toBeInTheDocument();
    });
  });

  describe('SystemStatusWidget', () => {
    it('renders the system status data with color-coded chips', () => {
      (useSystemStore as jest.Mock).mockReturnValue({
        engineStatus: 'Running',
        riskEngineStatus: 'Monitoring',
        lastWebhookTimestamp: '2025-11-18T12:00:00Z',
      });
      render(<SystemStatusWidget />);
      expect(screen.getByText(/system status/i)).toBeInTheDocument();
      expect(screen.getByText((content, element) => {
        return element?.tagName.toLowerCase() === 'p' && content.startsWith('Engine:');
      })).toBeInTheDocument();
      expect(screen.getByText(/running/i)).toBeInTheDocument();
      expect(screen.getByText((content, element) => {
        return element?.tagName.toLowerCase() === 'p' && content.startsWith('Risk Engine:');
      })).toBeInTheDocument();
      expect(screen.getByText(/monitoring/i)).toBeInTheDocument();
      expect(screen.getByText(/last signal: 2025-11-18t12:00:00z/i)).toBeInTheDocument();
      expect(screen.getByTestId('engine-status-chip')).toHaveAttribute('data-color', 'success');
      expect(screen.getByTestId('risk-engine-status-chip')).toHaveAttribute('data-color', 'info');
    });
  });

  describe('PnlCard', () => {
    it('renders the PnL data with color-coded values', () => {
      (useDataStore as jest.Mock).mockReturnValue({
        pnlMetrics: {
          unrealized_pnl: 123.45,
          realized_pnl: -67.89,
          total_pnl: 55.56,
        },
      });
      render(<PnlCard />);
      expect(screen.getByText(/unrealized pnl: \$123\.45/i)).toBeInTheDocument();
      expect(screen.getByTestId('unrealized-pnl')).toHaveStyle('color: green');
      expect(screen.getByText(/realized pnl: \$-67\.89/i)).toBeInTheDocument();
      expect(screen.getByTestId('realized-pnl')).toHaveStyle('color: red');
      expect(screen.getByText(/total pnl: \$55\.56/i)).toBeInTheDocument();
      expect(screen.getByTestId('total-pnl')).toHaveStyle('color: green');
    });
  });

  describe('EquityCurveChart', () => {
    it('renders the equity curve chart placeholder', () => {
      render(<EquityCurveChart />);
      expect(screen.getByText(/equity curve chart/i)).toBeInTheDocument();
    });
  });
});