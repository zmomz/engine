import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import SettingsPage from './SettingsPage';
import { MemoryRouter } from 'react-router-dom';
import useConfigStore from '../store/configStore';
import useConfirmStore from '../store/confirmStore';
import userEvent from '@testing-library/user-event';

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
      deleteKey: mockDeleteKey
    });

    (useConfirmStore.getState as jest.Mock) = jest.fn().mockReturnValue({
        requestConfirm: mockRequestConfirm
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
    const apiKeyInput = screen.getByLabelText(/api key \(public\)/i);
    await userEvent.clear(apiKeyInput);
    
    const saveKeysButton = screen.getByRole('button', { name: /save api keys/i });
    fireEvent.click(saveKeysButton);

    // Expect notification instead of alert
    await waitFor(() => {
      expect(mockShowNotification).toHaveBeenCalledWith(expect.stringMatching(/please enter both/i), 'warning');
    });
    expect(mockUpdateSettings).not.toHaveBeenCalled();
  });

  test('deletes api key after confirmation', async () => {
    mockRequestConfirm.mockResolvedValue(true);

    render(
      <MemoryRouter>
        <SettingsPage />
      </MemoryRouter>
    );

    // Assuming 'binance' is listed in configured exchanges with a delete button
    const deleteButtons = screen.getAllByLabelText('delete');
    fireEvent.click(deleteButtons[0]);

    await waitFor(() => {
        expect(mockRequestConfirm).toHaveBeenCalled();
    });
    
    expect(mockDeleteKey).toHaveBeenCalledWith('binance');
  });

  test('validates DCA grid weights sum to 100', async () => {
    render(
      <MemoryRouter>
        <SettingsPage />
      </MemoryRouter>
    );

    // 1. Switch to DCA Grid tab
    const dcaTab = screen.getByRole('tab', { name: /dca grid/i });
    fireEvent.click(dcaTab);

    // 2. Change the weight to something that doesn't sum to 100 (e.g. 50)
    const weightInputs = screen.getAllByLabelText(/weight %/i);
    expect(weightInputs).toHaveLength(1);
    
    await userEvent.clear(weightInputs[0]);
    await userEvent.type(weightInputs[0], '50');

    // 3. Try to submit
    const saveButton = screen.getByRole('button', { name: /save settings/i });
    fireEvent.click(saveButton);

    // 4. Expect validation error
    await waitFor(() => {
       expect(screen.getByText(/Total weight percent must sum to 100/i)).toBeInTheDocument();
    });
    
    expect(mockUpdateSettings).not.toHaveBeenCalled();
  });
});