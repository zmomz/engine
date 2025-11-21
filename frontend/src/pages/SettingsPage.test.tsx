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
        encrypted_api_keys: { public: 'pk_123', private: 'sk_123' },
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
        webhook_secret: 'secret'
      },
      supportedExchanges: ['binance', 'bybit'],
      loading: false,
      error: null,
      fetchSettings: jest.fn(),
      updateSettings: mockUpdateSettings,
      fetchSupportedExchanges: jest.fn(),
    });
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

  test('allows updating configuration', async () => {
    render(
      <MemoryRouter>
        <SettingsPage />
      </MemoryRouter>
    );

    // 1. Change API Key
    const apiKeyInput = screen.getByLabelText(/api key \(public\)/i);
    await userEvent.clear(apiKeyInput);
    await userEvent.type(apiKeyInput, 'new_pk_123');

    // 2. Switch to Risk Engine tab and update values
    const riskTab = screen.getByRole('tab', { name: /risk engine/i });
    fireEvent.click(riskTab);
    
    // Wait for tab panel to be visible (implicit in MUI tabs usually, but good to be safe)
    // Note: MUI Tabs mount/unmount panels or hide them.
    // The input should be available.
    
    const maxExposureInput = screen.getByLabelText(/max total exposure usd/i);
    await userEvent.clear(maxExposureInput);
    await userEvent.type(maxExposureInput, '2000');

    // 3. Submit Form
    const saveButton = screen.getByRole('button', { name: /save settings/i });
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(mockUpdateSettings).toHaveBeenCalledWith(expect.objectContaining({
        encrypted_api_keys: expect.objectContaining({
          public: 'new_pk_123'
        }),
        risk_config: expect.objectContaining({
          max_total_exposure_usd: 2000
        })
      }));
    });
  });

  test('validates input before submission', async () => {
    render(
      <MemoryRouter>
        <SettingsPage />
      </MemoryRouter>
    );

    // Clear required field
    const apiKeyInput = screen.getByLabelText(/api key \(public\)/i);
    await userEvent.clear(apiKeyInput);

    const saveButton = screen.getByRole('button', { name: /save settings/i });
    fireEvent.click(saveButton);

    // Expect validation error
    await waitFor(() => {
      expect(screen.getByText(/public key is required/i)).toBeInTheDocument();
    });
    expect(mockUpdateSettings).not.toHaveBeenCalled();
  });
});
