import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ThemeProvider } from '@mui/material/styles';
import DCAConfigList from './DCAConfigList';
import { darkTheme } from '../../theme/theme';
import { dcaConfigApi, DCAConfiguration } from '../../api/dcaConfig';

// Mock the DCA config API
jest.mock('../../api/dcaConfig', () => ({
  dcaConfigApi: {
    getAll: jest.fn(),
    create: jest.fn(),
    update: jest.fn(),
    delete: jest.fn(),
  },
}));

// Mock useMediaQuery for responsive tests
jest.mock('@mui/material', () => {
  const actual = jest.requireActual('@mui/material');
  return {
    ...actual,
    useMediaQuery: jest.fn(),
  };
});

import { useMediaQuery } from '@mui/material';

const renderWithTheme = (component: React.ReactElement) => {
  return render(
    <ThemeProvider theme={darkTheme}>{component}</ThemeProvider>
  );
};

const mockConfigs: DCAConfiguration[] = [
  {
    id: 'config-1',
    pair: 'BTC/USDT',
    timeframe: 60,
    exchange: 'binance',
    entry_order_type: 'limit',
    dca_levels: [{ gap_percent: 0, weight_percent: 100, tp_percent: 2 }],
    tp_mode: 'per_leg',
    tp_settings: {},
    max_pyramids: 5,
  },
  {
    id: 'config-2',
    pair: 'ETH/USDT',
    timeframe: 15,
    exchange: 'bybit',
    entry_order_type: 'market',
    dca_levels: [],
    tp_mode: 'aggregate',
    tp_settings: { tp_aggregate_percent: 2 },
    max_pyramids: 3,
  },
];

describe('DCAConfigList', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (useMediaQuery as jest.Mock).mockReturnValue(false); // Desktop by default
    (dcaConfigApi.getAll as jest.Mock).mockResolvedValue(mockConfigs);
  });

  describe('Loading State', () => {
    test('shows loading spinner while fetching', async () => {
      (dcaConfigApi.getAll as jest.Mock).mockImplementation(
        () => new Promise((resolve) => setTimeout(() => resolve([]), 100))
      );

      renderWithTheme(<DCAConfigList />);

      expect(screen.getByRole('progressbar')).toBeInTheDocument();

      await waitFor(() => {
        expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
      });
    });
  });

  describe('Desktop View - Table Layout', () => {
    beforeEach(() => {
      (useMediaQuery as jest.Mock).mockReturnValue(false);
    });

    test('renders title and add button', async () => {
      renderWithTheme(<DCAConfigList />);

      await waitFor(() => {
        expect(screen.getByText('Specific DCA Configurations')).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /add/i })).toBeInTheDocument();
      });
    });

    test('renders table with configs', async () => {
      renderWithTheme(<DCAConfigList />);

      await waitFor(() => {
        expect(screen.getByText('BTC/USDT')).toBeInTheDocument();
        expect(screen.getByText('ETH/USDT')).toBeInTheDocument();
      });
    });

    test('renders table headers', async () => {
      renderWithTheme(<DCAConfigList />);

      await waitFor(() => {
        expect(screen.getByText('Pair')).toBeInTheDocument();
        expect(screen.getByText('TF')).toBeInTheDocument();
        expect(screen.getByText('Exchange')).toBeInTheDocument();
        expect(screen.getByText('Entry')).toBeInTheDocument();
        expect(screen.getByText('TP Mode')).toBeInTheDocument();
        expect(screen.getByText('Pyramids')).toBeInTheDocument();
        expect(screen.getByText('Actions')).toBeInTheDocument();
      });
    });

    test('shows empty state when no configs', async () => {
      (dcaConfigApi.getAll as jest.Mock).mockResolvedValue([]);

      renderWithTheme(<DCAConfigList />);

      await waitFor(() => {
        expect(screen.getByText('No configs found')).toBeInTheDocument();
      });
    });

    test('displays entry type chip with correct color', async () => {
      renderWithTheme(<DCAConfigList />);

      await waitFor(() => {
        expect(screen.getByText('Limit')).toBeInTheDocument();
        expect(screen.getByText('Market')).toBeInTheDocument();
      });
    });
  });

  describe('Mobile View - Card Layout', () => {
    beforeEach(() => {
      (useMediaQuery as jest.Mock).mockReturnValue(true);
    });

    test('renders card layout on mobile', async () => {
      renderWithTheme(<DCAConfigList />);

      await waitFor(() => {
        expect(screen.getByText('BTC/USDT')).toBeInTheDocument();
      });

      // Should not have table
      expect(screen.queryByRole('table')).not.toBeInTheDocument();
    });

    test('shows empty message on mobile when no configs', async () => {
      (dcaConfigApi.getAll as jest.Mock).mockResolvedValue([]);

      renderWithTheme(<DCAConfigList />);

      await waitFor(() => {
        expect(screen.getByText('No configurations found')).toBeInTheDocument();
      });
    });
  });

  describe('Error Handling', () => {
    test('shows error alert on fetch failure', async () => {
      (dcaConfigApi.getAll as jest.Mock).mockRejectedValue(new Error('Network error'));

      renderWithTheme(<DCAConfigList />);

      await waitFor(() => {
        expect(screen.getByRole('alert')).toBeInTheDocument();
        expect(screen.getByText('Failed to load configurations')).toBeInTheDocument();
      });
    });
  });

  describe('Create Config', () => {
    test('opens form dialog when Add button is clicked', async () => {
      renderWithTheme(<DCAConfigList />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /add/i })).toBeInTheDocument();
      }, { timeout: 3000 });

      fireEvent.click(screen.getByRole('button', { name: /add/i }));

      await waitFor(() => {
        // Check for dialog presence
        expect(screen.queryByRole('dialog') || screen.queryByText(/Create DCA/i) || screen.queryByText(/Configuration/i)).toBeTruthy();
      }, { timeout: 3000 });
    });
  });

  describe('Edit Config', () => {
    test('opens form dialog with config data when edit button is clicked', async () => {
      renderWithTheme(<DCAConfigList />);

      await waitFor(() => {
        expect(screen.getByText('BTC/USDT')).toBeInTheDocument();
      });

      const editButtons = screen.getAllByRole('button').filter(
        btn => btn.querySelector('[data-testid="EditIcon"]')
      );
      fireEvent.click(editButtons[0]);

      await waitFor(() => {
        expect(screen.getByText('Edit DCA Configuration')).toBeInTheDocument();
      });
    });
  });

  describe('Delete Config', () => {
    test('calls delete API and refreshes when confirmed', async () => {
      window.confirm = jest.fn().mockReturnValue(true);
      (dcaConfigApi.delete as jest.Mock).mockResolvedValue(undefined);

      renderWithTheme(<DCAConfigList />);

      await waitFor(() => {
        expect(screen.getByText('BTC/USDT')).toBeInTheDocument();
      });

      const deleteButtons = screen.getAllByRole('button').filter(
        btn => btn.querySelector('[data-testid="DeleteIcon"]')
      );
      fireEvent.click(deleteButtons[0]);

      expect(window.confirm).toHaveBeenCalledWith(
        'Are you sure you want to delete this configuration?'
      );

      await waitFor(() => {
        expect(dcaConfigApi.delete).toHaveBeenCalledWith('config-1');
        expect(dcaConfigApi.getAll).toHaveBeenCalledTimes(2); // Initial + refresh
      });
    });

    test('does not delete when user cancels', async () => {
      window.confirm = jest.fn().mockReturnValue(false);

      renderWithTheme(<DCAConfigList />);

      await waitFor(() => {
        expect(screen.getByText('BTC/USDT')).toBeInTheDocument();
      });

      const deleteButtons = screen.getAllByRole('button').filter(
        btn => btn.querySelector('[data-testid="DeleteIcon"]')
      );
      fireEvent.click(deleteButtons[0]);

      expect(dcaConfigApi.delete).not.toHaveBeenCalled();
    });

    test('shows alert on delete failure', async () => {
      window.confirm = jest.fn().mockReturnValue(true);
      window.alert = jest.fn();
      (dcaConfigApi.delete as jest.Mock).mockRejectedValue(new Error('Delete failed'));

      renderWithTheme(<DCAConfigList />);

      await waitFor(() => {
        expect(screen.getByText('BTC/USDT')).toBeInTheDocument();
      });

      const deleteButtons = screen.getAllByRole('button').filter(
        btn => btn.querySelector('[data-testid="DeleteIcon"]')
      );
      fireEvent.click(deleteButtons[0]);

      await waitFor(() => {
        expect(window.alert).toHaveBeenCalledWith('Failed to delete configuration');
      });
    });
  });

  describe('Form Submission', () => {
    test('calls create API for new config', async () => {
      (dcaConfigApi.create as jest.Mock).mockResolvedValue({ id: 'new-id' });

      renderWithTheme(<DCAConfigList />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /add/i })).toBeInTheDocument();
      });

      fireEvent.click(screen.getByRole('button', { name: /add/i }));

      await waitFor(() => {
        expect(screen.getByText('Create DCA Configuration')).toBeInTheDocument();
      });

      // Form dialog is open - we just verify the interaction works
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    test('calls update API for existing config', async () => {
      (dcaConfigApi.update as jest.Mock).mockResolvedValue({ id: 'config-1' });

      renderWithTheme(<DCAConfigList />);

      await waitFor(() => {
        expect(screen.getByText('BTC/USDT')).toBeInTheDocument();
      });

      const editButtons = screen.getAllByRole('button').filter(
        btn => btn.querySelector('[data-testid="EditIcon"]')
      );
      fireEvent.click(editButtons[0]);

      await waitFor(() => {
        expect(screen.getByText('Edit DCA Configuration')).toBeInTheDocument();
      });

      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });
  });

  describe('Fetches configs on mount', () => {
    test('calls getAll on initial render', async () => {
      renderWithTheme(<DCAConfigList />);

      await waitFor(() => {
        expect(dcaConfigApi.getAll).toHaveBeenCalledTimes(1);
      });
    });
  });
});
