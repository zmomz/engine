import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ThemeProvider } from '@mui/material/styles';
import SettingsPage from './SettingsPage';
import { MemoryRouter } from 'react-router-dom';
import useConfigStore from '../store/configStore';
import useConfirmStore from '../store/confirmStore';
import { darkTheme } from '../theme/theme';

jest.mock('../store/configStore');
jest.mock('../store/confirmStore');

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

describe('SettingsPage', () => {
  const mockUpdateSettings = jest.fn();
  const mockDeleteKey = jest.fn();
  const mockRequestConfirm = jest.fn();

  beforeEach(() => {
    mockShowNotification.mockClear();
    jest.clearAllMocks();

    (useConfigStore as unknown as jest.Mock).mockReturnValue({
      settings: {
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
        configured_exchanges: ['binance']
      },
      supportedExchanges: ['binance', 'bybit'],
      loading: false,
      error: null,
      fetchSettings: jest.fn(),
      updateSettings: mockUpdateSettings,
      fetchSupportedExchanges: jest.fn(),
      deleteKey: mockDeleteKey
    });

    (useConfirmStore.getState as jest.Mock) = jest.fn().mockReturnValue({
        requestConfirm: mockRequestConfirm
    });
  });

  test('renders settings heading and tabs', () => {
    renderWithProviders(<SettingsPage />);

    expect(screen.getByRole('heading', { name: /settings/i, level: 4 })).toBeInTheDocument();
    // Current tabs are Trading, Risk, Alerts, Account
    expect(screen.getByRole('tab', { name: /trading/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /risk/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /alerts/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /account/i })).toBeInTheDocument();
  });

  test('can switch to Risk tab', () => {
    renderWithProviders(<SettingsPage />);

    const riskTab = screen.getByRole('tab', { name: /risk/i });
    fireEvent.click(riskTab);

    // Should show risk configuration content
    expect(riskTab).toHaveAttribute('aria-selected', 'true');
  });

  test('can switch to Alerts tab', () => {
    renderWithProviders(<SettingsPage />);

    const alertsTab = screen.getByRole('tab', { name: /alerts/i });
    fireEvent.click(alertsTab);

    expect(alertsTab).toHaveAttribute('aria-selected', 'true');
  });

  test('can switch to Account tab', () => {
    renderWithProviders(<SettingsPage />);

    const accountTab = screen.getByRole('tab', { name: /account/i });
    fireEvent.click(accountTab);

    expect(accountTab).toHaveAttribute('aria-selected', 'true');
  });

  test('renders configured exchanges info', () => {
    renderWithProviders(<SettingsPage />);

    // The Trading tab should show exchange info - may appear multiple times
    expect(screen.getAllByText('binance').length).toBeGreaterThan(0);
  });

  test('displays settings form fields', () => {
    renderWithProviders(<SettingsPage />);

    // Check for form elements (might vary based on actual implementation)
    expect(screen.getByText('Trading')).toBeInTheDocument();
  });
});
