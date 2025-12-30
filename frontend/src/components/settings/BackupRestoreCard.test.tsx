import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ThemeProvider } from '@mui/material/styles';
import BackupRestoreCard from './BackupRestoreCard';
import { darkTheme } from '../../theme/theme';

// Mock notification store
const mockShowNotification = jest.fn();
jest.mock('../../store/notificationStore', () => {
  const storeMock = jest.fn();
  (storeMock as any).getState = () => ({
    showNotification: mockShowNotification
  });
  return {
    __esModule: true,
    default: storeMock
  };
});

// Mock DCA config API
const mockGetAll = jest.fn();
jest.mock('../../api/dcaConfig', () => ({
  dcaConfigApi: {
    getAll: () => mockGetAll(),
  },
}));

const renderWithTheme = (component: React.ReactElement) => {
  return render(
    <ThemeProvider theme={darkTheme}>{component}</ThemeProvider>
  );
};

describe('BackupRestoreCard', () => {
  const mockOnRestore = jest.fn();
  const defaultSettings = {
    exchange: 'binance',
    risk_config: {
      max_open_positions_global: 10,
      max_total_exposure_usd: 5000,
    },
  };

  beforeEach(() => {
    jest.clearAllMocks();
    mockGetAll.mockResolvedValue([]);
  });

  describe('Rendering', () => {
    test('renders backup and restore title', () => {
      renderWithTheme(
        <BackupRestoreCard settings={defaultSettings} onRestore={mockOnRestore} />
      );

      expect(screen.getByText('Backup & Restore')).toBeInTheDocument();
    });

    test('renders description', () => {
      renderWithTheme(
        <BackupRestoreCard settings={defaultSettings} onRestore={mockOnRestore} />
      );

      expect(screen.getByText('Export or import your configuration')).toBeInTheDocument();
    });

    test('renders download backup section', () => {
      renderWithTheme(
        <BackupRestoreCard settings={defaultSettings} onRestore={mockOnRestore} />
      );

      expect(screen.getByText('Download Backup')).toBeInTheDocument();
      expect(screen.getByText(/export config and dca settings/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /download/i })).toBeInTheDocument();
    });

    test('renders restore configuration section', () => {
      renderWithTheme(
        <BackupRestoreCard settings={defaultSettings} onRestore={mockOnRestore} />
      );

      expect(screen.getByText('Restore Configuration')).toBeInTheDocument();
      expect(screen.getByText('Overwrites Risk and DCA settings.')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /upload/i })).toBeInTheDocument();
    });

    test('renders warning alert', () => {
      renderWithTheme(
        <BackupRestoreCard settings={defaultSettings} onRestore={mockOnRestore} />
      );

      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText(/api keys are unaffected/i)).toBeInTheDocument();
    });

    test('renders with null settings', () => {
      renderWithTheme(
        <BackupRestoreCard settings={null} onRestore={mockOnRestore} />
      );

      expect(screen.getByText('Backup & Restore')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /download/i })).toBeInTheDocument();
    });
  });

  describe('Backup Functionality', () => {
    test('handles backup error', async () => {
      mockGetAll.mockRejectedValue(new Error('API error'));

      renderWithTheme(
        <BackupRestoreCard settings={defaultSettings} onRestore={mockOnRestore} />
      );

      const downloadButton = screen.getByRole('button', { name: /download/i });
      fireEvent.click(downloadButton);

      await waitFor(() => {
        expect(mockShowNotification).toHaveBeenCalledWith(
          'Failed to create backup: API error',
          'error'
        );
      });
    });
  });

  describe('Restore Functionality', () => {
    const createFile = (content: string, name = 'backup.json', size?: number) => {
      const blob = new Blob([content], { type: 'application/json' });
      const file = new File([blob], name, { type: 'application/json' });
      if (size !== undefined) {
        Object.defineProperty(file, 'size', { value: size });
      }
      return file;
    };

    test('validates and restores valid backup file', async () => {
      mockOnRestore.mockResolvedValue(undefined);

      renderWithTheme(
        <BackupRestoreCard settings={defaultSettings} onRestore={mockOnRestore} />
      );

      // Backup schema only expects risk_config and dca_configurations
      // Other fields like 'exchange' are stripped by zod validation
      const validBackup = JSON.stringify({
        risk_config: {
          max_open_positions_global: 5,
        },
      });

      const file = createFile(validBackup);
      const input = document.querySelector('input[type="file"]') as HTMLInputElement;

      // Simulate file selection
      Object.defineProperty(input, 'files', {
        value: [file],
        writable: false,
      });

      fireEvent.change(input);

      await waitFor(() => {
        expect(mockOnRestore).toHaveBeenCalledWith({
          risk_config: {
            max_open_positions_global: 5,
          },
        });
      });
    });

    test('rejects file larger than 1MB', async () => {
      renderWithTheme(
        <BackupRestoreCard settings={defaultSettings} onRestore={mockOnRestore} />
      );

      const largeContent = 'x'.repeat(100);
      const file = createFile(largeContent, 'large.json', 1024 * 1024 + 1);
      const input = document.querySelector('input[type="file"]') as HTMLInputElement;

      Object.defineProperty(input, 'files', {
        value: [file],
        writable: false,
      });

      fireEvent.change(input);

      await waitFor(() => {
        expect(mockShowNotification).toHaveBeenCalledWith(
          'File too large. Maximum size is 1MB.',
          'error'
        );
      });

      expect(mockOnRestore).not.toHaveBeenCalled();
    });

    test('rejects invalid JSON', async () => {
      renderWithTheme(
        <BackupRestoreCard settings={defaultSettings} onRestore={mockOnRestore} />
      );

      const file = createFile('not valid json {{{');
      const input = document.querySelector('input[type="file"]') as HTMLInputElement;

      Object.defineProperty(input, 'files', {
        value: [file],
        writable: false,
      });

      fireEvent.change(input);

      await waitFor(() => {
        expect(mockShowNotification).toHaveBeenCalledWith(
          'Invalid JSON format',
          'error'
        );
      });
    });

    test('rejects invalid backup schema', async () => {
      renderWithTheme(
        <BackupRestoreCard settings={defaultSettings} onRestore={mockOnRestore} />
      );

      const invalidBackup = JSON.stringify({
        exchange: 123, // Should be string
        risk_config: 'invalid', // Should be object
      });

      const file = createFile(invalidBackup);
      const input = document.querySelector('input[type="file"]') as HTMLInputElement;

      Object.defineProperty(input, 'files', {
        value: [file],
        writable: false,
      });

      fireEvent.change(input);

      await waitFor(() => {
        expect(mockShowNotification).toHaveBeenCalledWith(
          expect.stringContaining('Invalid backup format'),
          'error'
        );
      });
    });

    test('handles empty file selection', async () => {
      renderWithTheme(
        <BackupRestoreCard settings={defaultSettings} onRestore={mockOnRestore} />
      );

      const input = document.querySelector('input[type="file"]') as HTMLInputElement;

      Object.defineProperty(input, 'files', {
        value: [],
        writable: false,
      });

      fireEvent.change(input);

      // Should not call onRestore
      expect(mockOnRestore).not.toHaveBeenCalled();
    });

    test('shows restoring state during restore', async () => {
      mockOnRestore.mockImplementation(() => new Promise((resolve) => setTimeout(resolve, 100)));

      renderWithTheme(
        <BackupRestoreCard settings={defaultSettings} onRestore={mockOnRestore} />
      );

      const validBackup = JSON.stringify({
        exchange: 'bybit',
        risk_config: {},
      });

      const file = createFile(validBackup);
      const input = document.querySelector('input[type="file"]') as HTMLInputElement;

      Object.defineProperty(input, 'files', {
        value: [file],
        writable: false,
      });

      fireEvent.change(input);

      // Button should show "Restoring..." during restore
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /restoring/i })).toBeInTheDocument();
      });
    });

    test('restores with DCA configurations', async () => {
      mockOnRestore.mockResolvedValue(undefined);

      renderWithTheme(
        <BackupRestoreCard settings={defaultSettings} onRestore={mockOnRestore} />
      );

      const backupWithDCA = JSON.stringify({
        exchange: 'binance',
        risk_config: {},
        dca_configurations: [
          {
            pair: 'ETH/USDT',
            timeframe: '60',
            exchange: 'binance',
            entry_order_type: 'market',
            dca_levels: [
              { percent_of_total: 50, deviation_percent: 1 },
              { percent_of_total: 50, deviation_percent: 2 },
            ],
            tp_mode: 'per_leg',
            max_pyramids: 2,
          },
        ],
      });

      const file = createFile(backupWithDCA);
      const input = document.querySelector('input[type="file"]') as HTMLInputElement;

      Object.defineProperty(input, 'files', {
        value: [file],
        writable: false,
      });

      fireEvent.change(input);

      await waitFor(() => {
        expect(mockOnRestore).toHaveBeenCalledWith(
          expect.objectContaining({
            dca_configurations: expect.arrayContaining([
              expect.objectContaining({
                pair: 'ETH/USDT',
              }),
            ]),
          })
        );
      });
    });
  });

  describe('File Input', () => {
    test('file input accepts JSON files only', () => {
      renderWithTheme(
        <BackupRestoreCard settings={defaultSettings} onRestore={mockOnRestore} />
      );

      const input = document.querySelector('input[type="file"]') as HTMLInputElement;
      expect(input).toHaveAttribute('accept', '.json');
    });

    test('file input is hidden', () => {
      renderWithTheme(
        <BackupRestoreCard settings={defaultSettings} onRestore={mockOnRestore} />
      );

      const input = document.querySelector('input[type="file"]') as HTMLInputElement;
      expect(input).toHaveAttribute('hidden');
    });
  });
});
