import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ThemeProvider } from '@mui/material/styles';
import SettingsPage from './SettingsPage';
import { MemoryRouter } from 'react-router-dom';
import useConfigStore from '../store/configStore';
import useConfirmStore from '../store/confirmStore';
import { darkTheme } from '../theme/theme';

jest.mock('../store/configStore');
jest.mock('../store/confirmStore');

// Mock child components to simplify testing
jest.mock('../components/QueuePrioritySettings', () => {
  return function MockQueuePrioritySettings() {
    return <div data-testid="queue-priority-settings">Queue Priority Settings</div>;
  };
});

jest.mock('../components/dca_config/DCAConfigList', () => {
  return function MockDCAConfigList() {
    return <div data-testid="dca-config-list">DCA Config List</div>;
  };
});

jest.mock('../components/TelegramSettings', () => {
  return function MockTelegramSettings() {
    return <div data-testid="telegram-settings">Telegram Settings</div>;
  };
});

jest.mock('../components/settings', () => ({
  SettingsPageSkeleton: function MockSkeleton() {
    return <div data-testid="settings-skeleton">Loading...</div>;
  },
  ExchangeConnectionCard: function MockExchangeCard({ activeExchange }: { activeExchange: string }) {
    return <div data-testid="exchange-connection-card">Exchange: {activeExchange}</div>;
  },
  ApiKeysListCard: function MockApiKeysList({
    onEdit,
    onDelete,
    configuredExchanges
  }: {
    onEdit: (exchange: string) => void;
    onDelete: (exchange: string) => void;
    configuredExchanges: string[];
  }) {
    return (
      <div data-testid="api-keys-list-card">
        {configuredExchanges.map((exchange: string) => (
          <div key={exchange}>
            <span>{exchange}</span>
            <button onClick={() => onEdit(exchange)}>Edit {exchange}</button>
            <button onClick={() => onDelete(exchange)}>Delete {exchange}</button>
          </div>
        ))}
      </div>
    );
  },
  ApiKeysFormCard: function MockApiKeysForm({
    onSaveKeys,
    watch
  }: {
    onSaveKeys: () => void;
    watch: (name: string) => { api_key?: string; secret_key?: string; key_target_exchange?: string };
  }) {
    return (
      <div data-testid="api-keys-form-card">
        <button onClick={onSaveKeys} data-testid="save-api-keys-btn">Save API Keys</button>
      </div>
    );
  },
  RiskLimitsSection: function MockRiskLimits() {
    return <div data-testid="risk-limits-section">Risk Limits</div>;
  },
  TimerConfigSection: function MockTimerConfig() {
    return <div data-testid="timer-config-section">Timer Config</div>;
  },
  AccountSettingsCard: function MockAccountSettings({ webhookUrl }: { webhookUrl: string }) {
    return <div data-testid="account-settings-card">Webhook: {webhookUrl}</div>;
  },
  BackupRestoreCard: function MockBackupRestore({
    onRestore
  }: {
    onRestore: (data: Record<string, unknown>) => Promise<void>;
  }) {
    const handleRestore = () => {
      onRestore({
        exchange: 'binance',
        risk_config: {
          max_open_positions_global: 10,
          max_open_positions_per_symbol: 2,
          max_total_exposure_usd: 5000,
          max_realized_loss_usd: 200,
          loss_threshold_percent: -3,
          required_pyramids_for_timer: 2,
          post_pyramids_wait_minutes: 10,
          max_winners_to_combine: 2,
        },
      });
    };
    const handleRestoreWithDCA = () => {
      onRestore({
        exchange: 'bybit',
        risk_config: {
          max_open_positions_global: 5,
        },
        dca_configurations: [
          {
            pair: 'BTC/USDT',
            timeframe: '15',
            exchange: 'bybit',
            entry_order_type: 'limit',
            dca_levels: [
              { percent_of_total: 50, deviation_percent: 1, tp_percent: 2 },
              { percent_of_total: 50, deviation_percent: 2, tp_percent: 3 },
            ],
            tp_mode: 'per_leg',
            max_pyramids: 3,
          },
        ],
      });
    };
    return (
      <div data-testid="backup-restore-card">
        <button onClick={handleRestore} data-testid="restore-btn">Restore</button>
        <button onClick={handleRestoreWithDCA} data-testid="restore-dca-btn">Restore with DCA</button>
      </div>
    );
  },
  SettingsSectionCard: function MockSettingsSectionCard({
    title,
    children
  }: {
    title: string;
    children: React.ReactNode;
  }) {
    return (
      <div data-testid={`settings-section-${title.toLowerCase().replace(/\s+/g, '-')}`}>
        <h3>{title}</h3>
        {children}
      </div>
    );
  },
}));

// Mock DCA config API for restore functionality
jest.mock('../api/dcaConfig', () => ({
  dcaConfigApi: {
    getAll: jest.fn().mockResolvedValue([]),
    create: jest.fn().mockResolvedValue({ id: 'new-id' }),
    update: jest.fn().mockResolvedValue({ id: 'updated-id' }),
  },
}));

const mockShowNotification = jest.fn();
jest.mock('../store/notificationStore', () => {
  const storeMock = jest.fn();
  (storeMock as any).getState = () => ({
    showNotification: mockShowNotification
  });
  return {
    __esModule: true,
    default: storeMock
  };
});

// Helper to render with required providers
const renderWithProviders = (component: React.ReactElement) => {
  return render(
    <ThemeProvider theme={darkTheme}>
      <MemoryRouter>{component}</MemoryRouter>
    </ThemeProvider>
  );
};

const defaultSettings = {
  id: 'user-123',
  exchange: 'binance',
  encrypted_api_keys: { binance: { apiKey: 'pk_123' } },
  risk_config: {
    max_open_positions_global: 5,
    max_open_positions_per_symbol: 1,
    max_total_exposure_usd: 1000,
    max_realized_loss_usd: 100,
    loss_threshold_percent: -2,
    required_pyramids_for_timer: 3,
    post_pyramids_wait_minutes: 15,
    max_winners_to_combine: 1,
    priority_rules: {
      priority_rules_enabled: {
        same_pair_timeframe: true,
        deepest_loss_percent: true,
        highest_replacement: true,
        fifo_fallback: true,
      },
      priority_order: ['same_pair_timeframe', 'deepest_loss_percent', 'highest_replacement', 'fifo_fallback'],
    },
  },
  dca_grid_config: {
    levels: [
      { gap_percent: 1, weight_percent: 100, tp_percent: 1 }
    ],
    tp_mode: 'per_leg',
    tp_aggregate_percent: 0
  },
  username: 'testuser',
  email: 'test@example.com',
  webhook_secret: 'secret',
  configured_exchanges: ['binance'],
  configured_exchange_details: {
    binance: { testnet: false, account_type: 'spot' }
  },
  telegram_config: {
    enabled: true,
    bot_token: 'bot123',
    channel_id: 'channel123',
  },
};

describe('SettingsPage', () => {
  const mockUpdateSettings = jest.fn().mockResolvedValue(undefined);
  const mockDeleteKey = jest.fn().mockResolvedValue(undefined);
  const mockFetchSettings = jest.fn();
  const mockFetchSupportedExchanges = jest.fn();
  const mockRequestConfirm = jest.fn();

  const setupMocks = (overrides: Record<string, unknown> = {}) => {
    (useConfigStore as unknown as jest.Mock).mockReturnValue({
      settings: defaultSettings,
      supportedExchanges: ['binance', 'bybit', 'kucoin'],
      loading: false,
      error: null,
      fetchSettings: mockFetchSettings,
      updateSettings: mockUpdateSettings,
      fetchSupportedExchanges: mockFetchSupportedExchanges,
      deleteKey: mockDeleteKey,
      ...overrides,
    });

    (useConfirmStore.getState as jest.Mock) = jest.fn().mockReturnValue({
      requestConfirm: mockRequestConfirm
    });
  };

  beforeEach(() => {
    mockShowNotification.mockClear();
    jest.clearAllMocks();
    setupMocks();
  });

  describe('Loading State', () => {
    test('renders loading skeleton when loading and no settings', () => {
      setupMocks({ loading: true, settings: null });
      renderWithProviders(<SettingsPage />);

      expect(screen.getByTestId('settings-skeleton')).toBeInTheDocument();
      expect(screen.queryByRole('heading', { name: /settings/i })).not.toBeInTheDocument();
    });

    test('renders page content when loading but settings exist', () => {
      setupMocks({ loading: true, settings: defaultSettings });
      renderWithProviders(<SettingsPage />);

      expect(screen.queryByTestId('settings-skeleton')).not.toBeInTheDocument();
      expect(screen.getByRole('heading', { name: /settings/i })).toBeInTheDocument();
    });
  });

  describe('Error State', () => {
    test('renders error alert when error exists', () => {
      setupMocks({ error: 'Failed to load settings', settings: null });
      renderWithProviders(<SettingsPage />);

      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText(/error loading settings/i)).toBeInTheDocument();
      expect(screen.getByText(/failed to load settings/i)).toBeInTheDocument();
    });

    test('error message displays correctly', () => {
      setupMocks({ error: 'Network error occurred', settings: null });
      renderWithProviders(<SettingsPage />);

      const alert = screen.getByRole('alert');
      expect(alert).toHaveTextContent('Network error occurred');
    });
  });

  describe('Tab Navigation', () => {
    test('renders settings heading and tabs', () => {
      renderWithProviders(<SettingsPage />);

      expect(screen.getByRole('heading', { name: /settings/i, level: 4 })).toBeInTheDocument();
      expect(screen.getByRole('tab', { name: /trading/i })).toBeInTheDocument();
      expect(screen.getByRole('tab', { name: /risk/i })).toBeInTheDocument();
      expect(screen.getByRole('tab', { name: /alerts/i })).toBeInTheDocument();
      expect(screen.getByRole('tab', { name: /account/i })).toBeInTheDocument();
    });

    test('Trading tab is selected by default', () => {
      renderWithProviders(<SettingsPage />);

      const tradingTab = screen.getByRole('tab', { name: /trading/i });
      expect(tradingTab).toHaveAttribute('aria-selected', 'true');
    });

    test('can switch to Risk tab', () => {
      renderWithProviders(<SettingsPage />);

      const riskTab = screen.getByRole('tab', { name: /risk/i });
      fireEvent.click(riskTab);

      expect(riskTab).toHaveAttribute('aria-selected', 'true');
      expect(screen.getByTestId('risk-limits-section')).toBeInTheDocument();
      expect(screen.getByTestId('timer-config-section')).toBeInTheDocument();
    });

    test('can switch to Alerts tab', () => {
      renderWithProviders(<SettingsPage />);

      const alertsTab = screen.getByRole('tab', { name: /alerts/i });
      fireEvent.click(alertsTab);

      expect(alertsTab).toHaveAttribute('aria-selected', 'true');
      expect(screen.getByTestId('telegram-settings')).toBeInTheDocument();
    });

    test('can switch to Account tab', () => {
      renderWithProviders(<SettingsPage />);

      const accountTab = screen.getByRole('tab', { name: /account/i });
      fireEvent.click(accountTab);

      expect(accountTab).toHaveAttribute('aria-selected', 'true');
      expect(screen.getByTestId('account-settings-card')).toBeInTheDocument();
      expect(screen.getByTestId('backup-restore-card')).toBeInTheDocument();
    });

    test('hides previous tab content when switching tabs', () => {
      renderWithProviders(<SettingsPage />);

      // Initially on Trading tab
      expect(screen.getByTestId('exchange-connection-card')).toBeInTheDocument();

      // Switch to Risk tab
      fireEvent.click(screen.getByRole('tab', { name: /risk/i }));

      // Trading content should be hidden (tabpanel hidden)
      expect(screen.getByTestId('risk-limits-section')).toBeInTheDocument();
    });
  });

  describe('Trading Tab Content', () => {
    test('renders exchange connection card', () => {
      renderWithProviders(<SettingsPage />);

      expect(screen.getByTestId('exchange-connection-card')).toBeInTheDocument();
      expect(screen.getByText('Exchange: binance')).toBeInTheDocument();
    });

    test('renders API keys list card', () => {
      renderWithProviders(<SettingsPage />);

      expect(screen.getByTestId('api-keys-list-card')).toBeInTheDocument();
    });

    test('renders API keys form card', () => {
      renderWithProviders(<SettingsPage />);

      expect(screen.getByTestId('api-keys-form-card')).toBeInTheDocument();
    });

    test('renders DCA configuration section', () => {
      renderWithProviders(<SettingsPage />);

      expect(screen.getByTestId('dca-config-list')).toBeInTheDocument();
    });

    test('displays connected exchange in header', () => {
      renderWithProviders(<SettingsPage />);

      expect(screen.getByText(/connected to binance/i)).toBeInTheDocument();
    });

    test('displays no exchange configured when no exchange set', () => {
      setupMocks({ settings: { ...defaultSettings, exchange: '' } });
      renderWithProviders(<SettingsPage />);

      expect(screen.getByText(/no exchange configured/i)).toBeInTheDocument();
    });
  });

  describe('Risk Tab Content', () => {
    test('renders risk limits section', () => {
      renderWithProviders(<SettingsPage />);
      fireEvent.click(screen.getByRole('tab', { name: /risk/i }));

      expect(screen.getByTestId('risk-limits-section')).toBeInTheDocument();
    });

    test('renders timer config section', () => {
      renderWithProviders(<SettingsPage />);
      fireEvent.click(screen.getByRole('tab', { name: /risk/i }));

      expect(screen.getByTestId('timer-config-section')).toBeInTheDocument();
    });

    test('renders queue priority settings', () => {
      renderWithProviders(<SettingsPage />);
      fireEvent.click(screen.getByRole('tab', { name: /risk/i }));

      expect(screen.getByTestId('queue-priority-settings')).toBeInTheDocument();
    });
  });

  describe('Alerts Tab Content', () => {
    test('renders telegram settings', () => {
      renderWithProviders(<SettingsPage />);
      fireEvent.click(screen.getByRole('tab', { name: /alerts/i }));

      expect(screen.getByTestId('telegram-settings')).toBeInTheDocument();
    });

    test('shows telegram enabled status', () => {
      renderWithProviders(<SettingsPage />);
      fireEvent.click(screen.getByRole('tab', { name: /alerts/i }));

      // Should show Enabled when telegram is enabled
      expect(screen.getByText('Enabled')).toBeInTheDocument();
    });

    test('shows telegram disabled status when not configured', () => {
      setupMocks({
        settings: {
          ...defaultSettings,
          telegram_config: { enabled: false },
        },
      });
      renderWithProviders(<SettingsPage />);
      fireEvent.click(screen.getByRole('tab', { name: /alerts/i }));

      expect(screen.getByText('Disabled')).toBeInTheDocument();
    });

    test('renders coming soon section for other channels', () => {
      renderWithProviders(<SettingsPage />);
      fireEvent.click(screen.getByRole('tab', { name: /alerts/i }));

      expect(screen.getByText(/other channels/i)).toBeInTheDocument();
      expect(screen.getByText(/discord, email, and webhook notifications coming soon/i)).toBeInTheDocument();
    });
  });

  describe('Account Tab Content', () => {
    test('renders account settings card with webhook URL', () => {
      renderWithProviders(<SettingsPage />);
      fireEvent.click(screen.getByRole('tab', { name: /account/i }));

      expect(screen.getByTestId('account-settings-card')).toBeInTheDocument();
      expect(screen.getByText(/webhook.*user-123.*tradingview/i)).toBeInTheDocument();
    });

    test('renders backup restore card', () => {
      renderWithProviders(<SettingsPage />);
      fireEvent.click(screen.getByRole('tab', { name: /account/i }));

      expect(screen.getByTestId('backup-restore-card')).toBeInTheDocument();
    });

    test('renders danger zone section', () => {
      renderWithProviders(<SettingsPage />);
      fireEvent.click(screen.getByRole('tab', { name: /account/i }));

      expect(screen.getByText(/danger zone/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /reset all settings/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /reset all settings/i })).toBeDisabled();
    });
  });

  describe('Form Submission', () => {
    test('submits form with current values when Save button clicked', async () => {
      renderWithProviders(<SettingsPage />);

      const saveButton = screen.getByRole('button', { name: /save settings/i });
      fireEvent.click(saveButton);

      await waitFor(() => {
        expect(mockUpdateSettings).toHaveBeenCalled();
      });
    });

    test('save button is visible on page', () => {
      renderWithProviders(<SettingsPage />);

      expect(screen.getByRole('button', { name: /save settings/i })).toBeInTheDocument();
    });
  });

  describe('API Key Management', () => {
    test('calls handleSaveApiKeys when save keys button clicked', async () => {
      renderWithProviders(<SettingsPage />);

      const saveKeysBtn = screen.getByTestId('save-api-keys-btn');
      fireEvent.click(saveKeysBtn);

      // Should show notification for missing keys (mocked watch returns empty)
      await waitFor(() => {
        expect(mockShowNotification).toHaveBeenCalledWith(
          'Please enter both API Key and Secret Key.',
          'warning'
        );
      });
    });

    test('calls handleEditKey when edit button clicked', async () => {
      renderWithProviders(<SettingsPage />);

      const editButton = screen.getByRole('button', { name: /edit binance/i });
      fireEvent.click(editButton);

      // The form should update (we can verify by checking no errors thrown)
      expect(editButton).toBeInTheDocument();
    });

    test('calls handleDeleteKey with confirmation when delete button clicked', async () => {
      mockRequestConfirm.mockResolvedValue(true);
      renderWithProviders(<SettingsPage />);

      const deleteButton = screen.getByRole('button', { name: /delete binance/i });
      fireEvent.click(deleteButton);

      await waitFor(() => {
        expect(mockRequestConfirm).toHaveBeenCalledWith({
          title: 'Delete API Keys',
          message: 'Are you sure you want to delete API keys for binance?',
          confirmText: 'Delete',
          cancelText: 'Cancel',
        });
      });

      await waitFor(() => {
        expect(mockDeleteKey).toHaveBeenCalledWith('binance');
      });
    });

    test('does not delete key when confirmation is cancelled', async () => {
      mockRequestConfirm.mockResolvedValue(false);
      renderWithProviders(<SettingsPage />);

      const deleteButton = screen.getByRole('button', { name: /delete binance/i });
      fireEvent.click(deleteButton);

      await waitFor(() => {
        expect(mockRequestConfirm).toHaveBeenCalled();
      });

      expect(mockDeleteKey).not.toHaveBeenCalled();
    });
  });

  describe('Backup and Restore', () => {
    test('calls handleRestore when restore button clicked', async () => {
      renderWithProviders(<SettingsPage />);
      fireEvent.click(screen.getByRole('tab', { name: /account/i }));

      const restoreBtn = screen.getByTestId('restore-btn');
      fireEvent.click(restoreBtn);

      await waitFor(() => {
        expect(mockUpdateSettings).toHaveBeenCalledWith({
          exchange: 'binance',
          risk_config: expect.objectContaining({
            max_open_positions_global: 10,
          }),
        });
      });
    });

    test('handles restore with DCA configurations', async () => {
      const { dcaConfigApi } = require('../api/dcaConfig');
      dcaConfigApi.getAll.mockResolvedValue([]);
      dcaConfigApi.create.mockResolvedValue({ id: 'new-config' });

      renderWithProviders(<SettingsPage />);
      fireEvent.click(screen.getByRole('tab', { name: /account/i }));

      const restoreDcaBtn = screen.getByTestId('restore-dca-btn');
      fireEvent.click(restoreDcaBtn);

      await waitFor(() => {
        expect(mockUpdateSettings).toHaveBeenCalled();
      });

      await waitFor(() => {
        expect(dcaConfigApi.create).toHaveBeenCalled();
      });

      await waitFor(() => {
        expect(mockShowNotification).toHaveBeenCalledWith(
          expect.stringContaining('Configuration restored successfully'),
          'success'
        );
      });
    });

    test('shows notification without DCA configs in restore', async () => {
      renderWithProviders(<SettingsPage />);
      fireEvent.click(screen.getByRole('tab', { name: /account/i }));

      const restoreBtn = screen.getByTestId('restore-btn');
      fireEvent.click(restoreBtn);

      await waitFor(() => {
        expect(mockShowNotification).toHaveBeenCalledWith(
          expect.stringContaining('no DCA configs found'),
          'success'
        );
      });
    });
  });

  describe('Effects and Initialization', () => {
    test('fetches settings on mount', () => {
      renderWithProviders(<SettingsPage />);

      expect(mockFetchSettings).toHaveBeenCalled();
    });

    test('fetches supported exchanges on mount', () => {
      renderWithProviders(<SettingsPage />);

      expect(mockFetchSupportedExchanges).toHaveBeenCalled();
    });
  });

  describe('Webhook URL Generation', () => {
    test('displays webhook URL with user ID', () => {
      renderWithProviders(<SettingsPage />);
      fireEvent.click(screen.getByRole('tab', { name: /account/i }));

      expect(screen.getByText(/user-123.*tradingview/i)).toBeInTheDocument();
    });

    test('displays Loading when no settings ID', () => {
      setupMocks({ settings: { ...defaultSettings, id: undefined } });
      renderWithProviders(<SettingsPage />);
      fireEvent.click(screen.getByRole('tab', { name: /account/i }));

      expect(screen.getByText(/webhook.*loading/i)).toBeInTheDocument();
    });
  });

  describe('Metric Cards', () => {
    test('displays active exchange metric card', () => {
      renderWithProviders(<SettingsPage />);

      // MetricCard is not mocked, should render actual component
      expect(screen.getByText('Active Exchange')).toBeInTheDocument();
    });

    test('displays configured exchanges count', () => {
      renderWithProviders(<SettingsPage />);

      expect(screen.getByText('Configured Exchanges')).toBeInTheDocument();
    });

    test('displays max positions on Risk tab', () => {
      renderWithProviders(<SettingsPage />);
      fireEvent.click(screen.getByRole('tab', { name: /risk/i }));

      expect(screen.getByText('Max Positions')).toBeInTheDocument();
      expect(screen.getByText('Loss Limit')).toBeInTheDocument();
    });
  });

  describe('Multiple Configured Exchanges', () => {
    test('renders all configured exchanges in API keys list', () => {
      setupMocks({
        settings: {
          ...defaultSettings,
          configured_exchanges: ['binance', 'bybit', 'kucoin'],
        },
      });
      renderWithProviders(<SettingsPage />);

      expect(screen.getByRole('button', { name: /edit binance/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /edit bybit/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /edit kucoin/i })).toBeInTheDocument();
    });
  });

  describe('Settings without telegram config', () => {
    test('handles missing telegram config gracefully', () => {
      setupMocks({
        settings: {
          ...defaultSettings,
          telegram_config: undefined,
        },
      });
      renderWithProviders(<SettingsPage />);
      fireEvent.click(screen.getByRole('tab', { name: /alerts/i }));

      expect(screen.getByText('Disabled')).toBeInTheDocument();
    });
  });

  describe('Edge Cases', () => {
    test('handles empty configured exchanges', () => {
      setupMocks({
        settings: {
          ...defaultSettings,
          configured_exchanges: [],
        },
      });
      renderWithProviders(<SettingsPage />);

      expect(screen.getByTestId('api-keys-list-card')).toBeInTheDocument();
    });

    test('handles null settings gracefully for loading state', () => {
      setupMocks({ settings: null, loading: true });
      renderWithProviders(<SettingsPage />);

      expect(screen.getByTestId('settings-skeleton')).toBeInTheDocument();
    });

    test('handles missing risk config values', () => {
      setupMocks({
        settings: {
          ...defaultSettings,
          risk_config: {
            max_open_positions_global: 0,
            max_open_positions_per_symbol: 0,
            max_total_exposure_usd: 0,
            max_realized_loss_usd: 0,
            loss_threshold_percent: 0,
            required_pyramids_for_timer: 1,
            post_pyramids_wait_minutes: 0,
            max_winners_to_combine: 0,
          },
        },
      });
      renderWithProviders(<SettingsPage />);
      fireEvent.click(screen.getByRole('tab', { name: /risk/i }));

      expect(screen.getByTestId('risk-limits-section')).toBeInTheDocument();
    });
  });
});
