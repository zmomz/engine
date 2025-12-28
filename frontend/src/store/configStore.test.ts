import useConfigStore from './configStore';
import useAuthStore from './authStore';
import api from '../services/api';

jest.mock('../services/api', () => ({
  put: jest.fn(),
  get: jest.fn(),
  delete: jest.fn(),
}));
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

  it('fetchSettings should load settings from API', async () => {
    const mockUser = { id: '1', username: 'test' };
    (api.get as jest.Mock).mockResolvedValue({ data: mockUser });
    (useAuthStore.getState as jest.Mock).mockReturnValue({ token: 'test-token', login: jest.fn() });

    await useConfigStore.getState().fetchSettings();

    expect(api.get).toHaveBeenCalledWith('/settings');
    expect(useConfigStore.getState().settings).toEqual(mockUser);
    expect(useConfigStore.getState().loading).toBe(false);
  });

  it('fetchSettings should handle API error', async () => {
    (api.get as jest.Mock).mockRejectedValue({ response: { data: { detail: 'Unauthorized' } } });
    (useAuthStore.getState as jest.Mock).mockReturnValue({ token: null });

    await useConfigStore.getState().fetchSettings();

    expect(useConfigStore.getState().error).toBe('Unauthorized');
  });

  it('updateSettings should call API and update stores', async () => {
    const mockUpdatedSettings = { username: 'newname' };
    const mockResponse = { data: { ...mockUpdatedSettings, id: '1' } };
    (api.put as jest.Mock).mockResolvedValue(mockResponse);
    (useAuthStore.getState as jest.Mock).mockReturnValue({ token: 'token', login: jest.fn() });
    window.alert = jest.fn();

    await useConfigStore.getState().updateSettings(mockUpdatedSettings);

    expect(api.put).toHaveBeenCalledWith('/settings', mockUpdatedSettings);
    expect(useConfigStore.getState().settings).toEqual(mockResponse.data);
    expect(useAuthStore.getState().login).toHaveBeenCalled();
  });

  it('fetchSupportedExchanges should call API and update state', async () => {
    const mockExchanges = ['binance', 'bybit'];
    (api.get as jest.Mock).mockResolvedValue({ data: mockExchanges });

    await useConfigStore.getState().fetchSupportedExchanges();

    expect(api.get).toHaveBeenCalledWith('/settings/exchanges');
    expect(useConfigStore.getState().supportedExchanges).toEqual(mockExchanges);
  });

  it('deleteKey should call API and update stores', async () => {
    const mockResponse = { data: { username: 'test' } };
    (api.delete as jest.Mock).mockResolvedValue(mockResponse);
    (useAuthStore.getState as jest.Mock).mockReturnValue({ token: 'token', login: jest.fn() });
    window.alert = jest.fn();

    await useConfigStore.getState().deleteKey('binance');

    expect(api.delete).toHaveBeenCalledWith('/settings/keys/binance');
    expect(useConfigStore.getState().settings).toEqual(mockResponse.data);
    expect(useAuthStore.getState().login).toHaveBeenCalled();
  });
});
