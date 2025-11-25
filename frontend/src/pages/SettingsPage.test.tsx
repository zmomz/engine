import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import SettingsPage from './SettingsPage';
import { MemoryRouter } from 'react-router-dom';
import useConfigStore from '../store/configStore';
import userEvent from '@testing-library/user-event';

jest.mock('../store/configStore');

describe('SettingsPage', () => {
  const mockUpdateSettings = jest.fn();

  beforeEach(() => {
    (useConfigStore as unknown as jest.Mock).mockReturnValue({
      settings: {
        exchange: 'binance',
        encrypted_api_keys: { binance: { apiKey: 'pk_123' } },
        risk_config: {
          max_open_positions_global: 5,
          max_open_positions_per_symbol: 1,
          max_total_exposure_usd: 1000,
          max_daily_loss_usd: 100,
          loss_threshold_percent: -2,
          timer_start_condition: 'after_all_dca_filled',
          post_full_wait_minutes: 0,
          max_winners_to_combine: 1,
          use_trade_age_filter: false,
          age_threshold_minutes: 0,
          require_full_pyramids: false,
          reset_timer_on_replacement: false,
          partial_close_enabled: false,
          min_close_notional: 0
        },
        dca_grid_config: [
          { gap_percent: 1, weight_percent: 100, tp_percent: 1 }
        ],
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
    });
    jest.clearAllMocks();
    window.alert = jest.fn();
  });

  test('renders settings heading and tabs', () => {
    render(
      <MemoryRouter>
        <SettingsPage />
      </MemoryRouter>
    );

    expect(screen.getByRole('heading', { name: /settings/i, level: 4 })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /exchange/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /risk engine/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /dca grid/i })).toBeInTheDocument();
  });

  test('allows updating api keys separately', async () => {
    render(
      <MemoryRouter>
        <SettingsPage />
      </MemoryRouter>
    );

    // 1. Change API Key
    const apiKeyInput = screen.getByLabelText(/api key \(public\)/i);
    await userEvent.clear(apiKeyInput);
    await userEvent.type(apiKeyInput, 'new_pk_123');

    const secretKeyInput = screen.getByLabelText(/secret key \(private\)/i);
    await userEvent.clear(secretKeyInput);
    await userEvent.type(secretKeyInput, 'new_sk_123');
    
    // 2. Submit Keys
    const saveKeysButton = screen.getByRole('button', { name: /save api keys/i });
    fireEvent.click(saveKeysButton);

    await waitFor(() => {
      expect(mockUpdateSettings).toHaveBeenCalledWith(expect.objectContaining({
        api_key: 'new_pk_123',
        secret_key: 'new_sk_123'
      }));
    });
  });

  test('allows updating risk configuration separately', async () => {
    render(
      <MemoryRouter>
        <SettingsPage />
      </MemoryRouter>
    );

    // 1. Switch to Risk Engine tab and update values
    const riskTab = screen.getByRole('tab', { name: /risk engine/i });
    fireEvent.click(riskTab);
    
    const maxExposureInput = screen.getByLabelText(/max total exposure usd/i);
    fireEvent.change(maxExposureInput, { target: { value: '2000' } });

    // 2. Submit Settings (Global)
    const saveButton = screen.getByRole('button', { name: /save settings/i });
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(mockUpdateSettings).toHaveBeenCalledWith(expect.objectContaining({
        risk_config: expect.objectContaining({
          max_total_exposure_usd: 2000
        })
      }));
    });
  });

  test('validates api key input before submission', async () => {
    render(
      <MemoryRouter>
        <SettingsPage />
      </MemoryRouter>
    );

    // Leave fields empty (default state in test render if not pre-filled by reset in useEffect)
    // Actually our test render loads from store which might not prefill the form fields for security or default logic.
    // Let's assume they are empty or we clear them.
    const apiKeyInput = screen.getByLabelText(/api key \(public\)/i);
    await userEvent.clear(apiKeyInput);
    
    const saveKeysButton = screen.getByRole('button', { name: /save api keys/i });
    fireEvent.click(saveKeysButton);

    // Expect alert
    await waitFor(() => {
      expect(window.alert).toHaveBeenCalledWith(expect.stringMatching(/please enter both/i));
    });
    expect(mockUpdateSettings).not.toHaveBeenCalled();
  });
});
