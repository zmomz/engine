import useConfigStore from './configStore';
import useAuthStore from './authStore';
import axios from 'axios';

jest.mock('axios');
jest.mock('./authStore');

describe('configStore', () => {
  beforeEach(() => {
    useConfigStore.setState({
      settings: null,
      supportedExchanges: [],
      loading: false,
      error: null,
    });
    jest.clearAllMocks();
  });

  it('fetchSettings should load settings from authStore', async () => {
    const mockUser = { id: '1', username: 'test' };
    (useAuthStore.getState as jest.Mock).mockReturnValue({ user: mockUser });

    await useConfigStore.getState().fetchSettings();

    expect(useConfigStore.getState().settings).toEqual(mockUser);
    expect(useConfigStore.getState().loading).toBe(false);
  });

  it('fetchSettings should handle missing user', async () => {
    (useAuthStore.getState as jest.Mock).mockReturnValue({ user: null });

    await useConfigStore.getState().fetchSettings();

    expect(useConfigStore.getState().error).toBe('User not authenticated');
  });

  it('updateSettings should call API and update stores', async () => {
    const mockUpdatedSettings = { username: 'newname' };
    const mockResponse = { data: { ...mockUpdatedSettings, id: '1' } };
    (axios.put as jest.Mock).mockResolvedValue(mockResponse);
    (useAuthStore.getState as jest.Mock).mockReturnValue({ token: 'token', login: jest.fn() });
    window.alert = jest.fn();

    await useConfigStore.getState().updateSettings(mockUpdatedSettings);

    expect(axios.put).toHaveBeenCalledWith('/api/v1/settings', mockUpdatedSettings);
    expect(useConfigStore.getState().settings).toEqual(mockResponse.data);
    expect(useAuthStore.getState().login).toHaveBeenCalled();
  });

  it('fetchSupportedExchanges should call API and update state', async () => {
    const mockExchanges = ['binance', 'bybit'];
    (axios.get as jest.Mock).mockResolvedValue({ data: mockExchanges });

    await useConfigStore.getState().fetchSupportedExchanges();

    expect(axios.get).toHaveBeenCalledWith('/api/v1/settings/exchanges');
    expect(useConfigStore.getState().supportedExchanges).toEqual(mockExchanges);
  });
});
