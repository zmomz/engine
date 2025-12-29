import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ThemeProvider, createTheme } from '@mui/material';
import { useForm, FormProvider } from 'react-hook-form';
import TelegramSettings from './TelegramSettings';
import api from '../services/api';
import useNotificationStore from '../store/notificationStore';

// Mock dependencies
jest.mock('../services/api');
jest.mock('../store/notificationStore');

const mockedApi = api as jest.Mocked<typeof api>;

const theme = createTheme({
  palette: {
    mode: 'dark',
  },
});

// Wrapper component that provides form context
const TestWrapper: React.FC<{ defaultValues?: any; children?: React.ReactNode }> = ({
  defaultValues = {
    telegramSettings: {
      enabled: true,
      bot_token: 'test-token',
      channel_id: '-100123456789',
      channel_name: 'Test Channel',
      engine_signature: 'Test Signature',
      send_entry_signals: true,
      send_exit_signals: true,
      send_status_updates: false,
      send_dca_fill_updates: false,
      send_pyramid_updates: false,
      send_tp_hit_updates: false,
      send_failure_alerts: true,
      send_risk_alerts: true,
      update_existing_message: true,
      update_on_pyramid: false,
      show_unrealized_pnl: true,
      show_invested_amount: false,
      show_duration: true,
      alert_loss_threshold_percent: null,
      alert_profit_threshold_percent: null,
      quiet_hours_enabled: false,
      quiet_hours_start: null,
      quiet_hours_end: null,
      quiet_hours_urgent_only: false,
      test_mode: false,
    },
  },
  children,
}) => {
  const methods = useForm({ defaultValues });

  return (
    <ThemeProvider theme={theme}>
      <FormProvider {...methods}>
        <TelegramSettings
          control={methods.control}
          watch={methods.watch}
          getValues={methods.getValues}
        />
      </FormProvider>
    </ThemeProvider>
  );
};

describe('TelegramSettings', () => {
  const mockShowNotification = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    (useNotificationStore as unknown as jest.Mock).mockReturnValue(mockShowNotification);
  });

  describe('basic rendering', () => {
    it('renders Enable Telegram Broadcasting switch', () => {
      render(<TestWrapper />);
      expect(screen.getByLabelText('Enable Telegram Broadcasting')).toBeInTheDocument();
    });

    it('renders Connection section', () => {
      render(<TestWrapper />);
      expect(screen.getByText('Connection')).toBeInTheDocument();
    });

    it('renders Bot Token field', () => {
      render(<TestWrapper />);
      expect(screen.getByLabelText('Bot Token')).toBeInTheDocument();
    });

    it('renders Channel ID field', () => {
      render(<TestWrapper />);
      expect(screen.getByLabelText('Channel ID')).toBeInTheDocument();
    });

    it('renders Channel Name field', () => {
      render(<TestWrapper />);
      expect(screen.getByLabelText('Channel Name')).toBeInTheDocument();
    });

    it('renders Engine Signature field', () => {
      render(<TestWrapper />);
      expect(screen.getByLabelText('Engine Signature')).toBeInTheDocument();
    });

    it('renders Message Types section', () => {
      render(<TestWrapper />);
      expect(screen.getByText('Message Types')).toBeInTheDocument();
    });
  });

  describe('message type switches', () => {
    it('renders all position lifecycle switches', () => {
      render(<TestWrapper />);
      expect(screen.getByLabelText('Entry Signals')).toBeInTheDocument();
      expect(screen.getByLabelText('Exit Signals')).toBeInTheDocument();
      expect(screen.getByLabelText('Status Changes')).toBeInTheDocument();
    });

    it('renders all fill update switches', () => {
      render(<TestWrapper />);
      expect(screen.getByLabelText('DCA Leg Fills')).toBeInTheDocument();
      expect(screen.getByLabelText('New Pyramids')).toBeInTheDocument();
      expect(screen.getByLabelText('TP Hits')).toBeInTheDocument();
    });

    it('renders alert switches', () => {
      render(<TestWrapper />);
      expect(screen.getByLabelText('Failure Alerts')).toBeInTheDocument();
      expect(screen.getByLabelText('Risk Alerts')).toBeInTheDocument();
    });
  });

  describe('action buttons', () => {
    it('renders Test Connection button', () => {
      render(<TestWrapper />);
      expect(screen.getByText('Test Connection')).toBeInTheDocument();
    });

    it('renders Send Test Message button', () => {
      render(<TestWrapper />);
      expect(screen.getByText('Send Test Message')).toBeInTheDocument();
    });
  });

  describe('test connection', () => {
    it('calls API on Test Connection click', async () => {
      mockedApi.post.mockResolvedValue({});

      render(<TestWrapper />);
      fireEvent.click(screen.getByText('Test Connection'));

      await waitFor(() => {
        expect(mockedApi.post).toHaveBeenCalledWith('/telegram/test-connection', expect.any(Object));
      });
    });

    it(
      'shows success notification on successful connection',
      async () => {
        mockedApi.post.mockResolvedValue({});

        render(<TestWrapper />);
        fireEvent.click(screen.getByText('Test Connection'));

        await waitFor(
          () => {
            expect(mockShowNotification).toHaveBeenCalledWith(
              'Successfully connected to Telegram bot',
              'success'
            );
          },
          { timeout: 10000 }
        );
      },
      15000
    );

    it('shows error notification on failed connection', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      mockedApi.post.mockRejectedValue({
        response: { data: { detail: 'Invalid token' } },
      });

      render(<TestWrapper />);
      fireEvent.click(screen.getByText('Test Connection'));

      await waitFor(() => {
        expect(mockShowNotification).toHaveBeenCalledWith('Invalid token', 'error');
      });

      consoleSpy.mockRestore();
    });

    it('shows default error message when no detail', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      mockedApi.post.mockRejectedValue(new Error('Network error'));

      render(<TestWrapper />);
      fireEvent.click(screen.getByText('Test Connection'));

      await waitFor(() => {
        expect(mockShowNotification).toHaveBeenCalledWith(
          'Failed to connect to Telegram bot',
          'error'
        );
      });

      consoleSpy.mockRestore();
    });

    it('shows Testing... while testing connection', async () => {
      mockedApi.post.mockImplementation(
        () => new Promise((resolve) => setTimeout(() => resolve({}), 100))
      );

      render(<TestWrapper />);
      fireEvent.click(screen.getByText('Test Connection'));

      expect(screen.getByText('Testing...')).toBeInTheDocument();

      await waitFor(() => {
        expect(screen.getByText('Test Connection')).toBeInTheDocument();
      });
    });

    it('shows success alert after successful connection', async () => {
      mockedApi.post.mockResolvedValue({});

      render(<TestWrapper />);
      fireEvent.click(screen.getByText('Test Connection'));

      await waitFor(() => {
        expect(screen.getByText('Bot connection successful!')).toBeInTheDocument();
      });
    });

    it('shows error alert after failed connection', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      mockedApi.post.mockRejectedValue(new Error('Failed'));

      render(<TestWrapper />);
      fireEvent.click(screen.getByText('Test Connection'));

      await waitFor(() => {
        expect(screen.getByText('Failed to connect to bot. Check your token.')).toBeInTheDocument();
      });

      consoleSpy.mockRestore();
    });
  });

  describe('test message', () => {
    it('calls API on Send Test Message click', async () => {
      mockedApi.post.mockResolvedValue({});

      render(<TestWrapper />);
      fireEvent.click(screen.getByText('Send Test Message'));

      await waitFor(() => {
        expect(mockedApi.post).toHaveBeenCalledWith('/telegram/test-message', expect.any(Object));
      });
    });

    it('shows success notification on successful message', async () => {
      mockedApi.post.mockResolvedValue({});

      render(<TestWrapper />);
      fireEvent.click(screen.getByText('Send Test Message'));

      await waitFor(() => {
        expect(mockShowNotification).toHaveBeenCalledWith(
          'Test message sent successfully',
          'success'
        );
      });
    });

    it(
      'shows error notification on failed message',
      async () => {
        const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
        mockedApi.post.mockRejectedValue({
          response: { data: { detail: 'Channel not found' } },
        });

        render(<TestWrapper />);
        fireEvent.click(screen.getByText('Send Test Message'));

        await waitFor(
          () => {
            expect(mockShowNotification).toHaveBeenCalledWith('Channel not found', 'error');
          },
          { timeout: 10000 }
        );

        consoleSpy.mockRestore();
      },
      15000
    );

    it('shows Sending... while sending', async () => {
      mockedApi.post.mockImplementation(
        () => new Promise((resolve) => setTimeout(() => resolve({}), 100))
      );

      render(<TestWrapper />);
      fireEvent.click(screen.getByText('Send Test Message'));

      expect(screen.getByText('Sending...')).toBeInTheDocument();

      await waitFor(() => {
        expect(screen.getByText('Send Test Message')).toBeInTheDocument();
      });
    });
  });

  describe('disabled state', () => {
    it('disables fields when Telegram is disabled', () => {
      render(
        <TestWrapper
          defaultValues={{
            telegramSettings: {
              enabled: false,
              bot_token: '',
              channel_id: '',
            },
          }}
        />
      );

      expect(screen.getByLabelText('Bot Token')).toBeDisabled();
      expect(screen.getByLabelText('Channel ID')).toBeDisabled();
      expect(screen.getByText('Test Connection')).toBeDisabled();
      expect(screen.getByText('Send Test Message')).toBeDisabled();
    });
  });

  describe('advanced options', () => {
    it('renders Advanced Options section', () => {
      render(<TestWrapper />);
      expect(screen.getByText('Advanced Options')).toBeInTheDocument();
    });

    it('expands advanced options on click', () => {
      render(<TestWrapper />);

      // Click to expand
      fireEvent.click(screen.getByText('Advanced Options'));

      // Now visible - check for the input element in the DOM
      expect(screen.getByLabelText('Update existing message (less spam)')).toBeInTheDocument();
    });

    it('toggles advanced options on click', () => {
      render(<TestWrapper />);

      // Expand
      fireEvent.click(screen.getByText('Advanced Options'));
      expect(screen.getByLabelText('Update existing message (less spam)')).toBeInTheDocument();

      // Collapse and expand again - verify the element is still accessible
      fireEvent.click(screen.getByText('Advanced Options'));
      fireEvent.click(screen.getByText('Advanced Options'));
      expect(screen.getByLabelText('Update existing message (less spam)')).toBeInTheDocument();
    });

    it('renders advanced switches when expanded', () => {
      render(<TestWrapper />);
      fireEvent.click(screen.getByText('Advanced Options'));

      expect(screen.getByLabelText('Update existing message (less spam)')).toBeInTheDocument();
      expect(screen.getByLabelText('Update on new pyramid')).toBeInTheDocument();
      expect(screen.getByLabelText('Unrealized P&L')).toBeInTheDocument();
      expect(screen.getByLabelText('Invested Amount')).toBeInTheDocument();
      expect(screen.getByLabelText('Position Duration')).toBeInTheDocument();
    });

    it('renders threshold fields when expanded', () => {
      render(<TestWrapper />);
      fireEvent.click(screen.getByText('Advanced Options'));

      expect(screen.getByLabelText('Alert if loss exceeds (%)')).toBeInTheDocument();
      expect(screen.getByLabelText('Alert if profit exceeds (%)')).toBeInTheDocument();
    });

    it('renders test mode switch when expanded', () => {
      render(<TestWrapper />);
      fireEvent.click(screen.getByText('Advanced Options'));

      expect(screen.getByLabelText('Test Mode (log messages without sending)')).toBeInTheDocument();
    });
  });

  describe('quiet hours', () => {
    it('renders Enable Quiet Hours switch', () => {
      render(<TestWrapper />);
      fireEvent.click(screen.getByText('Advanced Options'));

      expect(screen.getByLabelText('Enable Quiet Hours')).toBeInTheDocument();
    });

    it('shows quiet hours fields when enabled', () => {
      render(
        <TestWrapper
          defaultValues={{
            telegramSettings: {
              enabled: true,
              quiet_hours_enabled: true,
              quiet_hours_start: '22:00',
              quiet_hours_end: '08:00',
              quiet_hours_urgent_only: false,
            },
          }}
        />
      );
      fireEvent.click(screen.getByText('Advanced Options'));

      expect(screen.getByLabelText('Start Time')).toBeInTheDocument();
      expect(screen.getByLabelText('End Time')).toBeInTheDocument();
      expect(screen.getByLabelText('Send urgent alerts during quiet hours')).toBeInTheDocument();
    });

    it('hides quiet hours fields when disabled', () => {
      render(
        <TestWrapper
          defaultValues={{
            telegramSettings: {
              enabled: true,
              quiet_hours_enabled: false,
            },
          }}
        />
      );
      fireEvent.click(screen.getByText('Advanced Options'));

      expect(screen.queryByLabelText('Start Time')).not.toBeInTheDocument();
      expect(screen.queryByLabelText('End Time')).not.toBeInTheDocument();
    });
  });

  describe('threshold fields', () => {
    it('handles empty threshold value', () => {
      render(<TestWrapper />);
      fireEvent.click(screen.getByText('Advanced Options'));

      const lossField = screen.getByLabelText('Alert if loss exceeds (%)');
      fireEvent.change(lossField, { target: { value: '' } });

      expect(lossField).toHaveValue(null);
    });

    it('handles numeric threshold value', () => {
      render(<TestWrapper />);
      fireEvent.click(screen.getByText('Advanced Options'));

      const profitField = screen.getByLabelText('Alert if profit exceeds (%)');
      fireEvent.change(profitField, { target: { value: '10.5' } });

      expect(profitField).toHaveValue(10.5);
    });
  });
});
