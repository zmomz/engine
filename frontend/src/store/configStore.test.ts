import useConfigStore from './configStore';
import useAuthStore from './authStore';
import useNotificationStore from './notificationStore';
import api from '../services/api';

jest.mock('../services/api', () => ({
  put: jest.fn(),
  get: jest.fn(),
  delete: jest.fn(),
}));
jest.mock('./authStore');
jest.mock('./notificationStore');

describe('configStore', () => {
  const mockShowNotification = jest.fn();

  beforeEach(() => {
    useConfigStore.setState({
      settings: null,
      supportedExchanges: [],
      loading: false,
      error: null,
    });
    jest.clearAllMocks();
    (useNotificationStore.getState as jest.Mock).mockReturnValue({
      showNotification: mockShowNotification,
    });
  });

  describe('fetchSettings', () => {
    it('should load settings from API', async () => {
      const mockUser = { id: '1', username: 'test' };
      (api.get as jest.Mock).mockResolvedValue({ data: mockUser });
      (useAuthStore.getState as jest.Mock).mockReturnValue({ token: 'test-token', login: jest.fn() });

      await useConfigStore.getState().fetchSettings();

      expect(api.get).toHaveBeenCalledWith('/settings');
      expect(useConfigStore.getState().settings).toEqual(mockUser);
      expect(useConfigStore.getState().loading).toBe(false);
    });

    it('should update auth store when token exists', async () => {
      const mockUser = { id: '1', username: 'test' };
      const mockLogin = jest.fn();
      (api.get as jest.Mock).mockResolvedValue({ data: mockUser });
      (useAuthStore.getState as jest.Mock).mockReturnValue({ token: 'test-token', login: mockLogin });

      await useConfigStore.getState().fetchSettings();

      expect(mockLogin).toHaveBeenCalledWith('test-token', mockUser);
    });

    it('should not update auth store when no token', async () => {
      const mockUser = { id: '1', username: 'test' };
      const mockLogin = jest.fn();
      (api.get as jest.Mock).mockResolvedValue({ data: mockUser });
      (useAuthStore.getState as jest.Mock).mockReturnValue({ token: null, login: mockLogin });

      await useConfigStore.getState().fetchSettings();

      expect(mockLogin).not.toHaveBeenCalled();
    });

    it('should handle API error', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      (api.get as jest.Mock).mockRejectedValue({ response: { data: { detail: 'Unauthorized' } } });
      (useAuthStore.getState as jest.Mock).mockReturnValue({ token: null });

      await useConfigStore.getState().fetchSettings();

      expect(useConfigStore.getState().error).toBe('Unauthorized');
      consoleSpy.mockRestore();
    });

    it('should handle API error without detail', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      (api.get as jest.Mock).mockRejectedValue(new Error('Network error'));
      (useAuthStore.getState as jest.Mock).mockReturnValue({ token: null });

      await useConfigStore.getState().fetchSettings();

      expect(useConfigStore.getState().error).toBe('Failed to fetch settings');
      consoleSpy.mockRestore();
    });
  });

  describe('updateSettings', () => {
    it('should call API and update stores', async () => {
      const mockUpdatedSettings = { username: 'newname' };
      const mockResponse = { data: { ...mockUpdatedSettings, id: '1' } };
      (api.put as jest.Mock).mockResolvedValue(mockResponse);
      (useAuthStore.getState as jest.Mock).mockReturnValue({ token: 'token', login: jest.fn() });

      await useConfigStore.getState().updateSettings(mockUpdatedSettings);

      expect(api.put).toHaveBeenCalledWith('/settings', mockUpdatedSettings);
      expect(useConfigStore.getState().settings).toEqual(mockResponse.data);
      expect(useAuthStore.getState().login).toHaveBeenCalled();
      expect(mockShowNotification).toHaveBeenCalledWith('Settings updated successfully!', 'success');
    });

    it('should handle API error with array detail', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      (api.put as jest.Mock).mockRejectedValue({
        response: {
          data: {
            detail: [
              { msg: 'Invalid email' },
              { msg: 'Username too short' },
            ],
          },
        },
      });
      (useAuthStore.getState as jest.Mock).mockReturnValue({ token: 'token', login: jest.fn() });

      await useConfigStore.getState().updateSettings({ username: 'x' });

      expect(useConfigStore.getState().error).toBe('Invalid email, Username too short');
      expect(mockShowNotification).toHaveBeenCalledWith(
        'Failed to update settings: Invalid email, Username too short',
        'error'
      );
      consoleSpy.mockRestore();
    });

    it('should handle API error with string detail', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      (api.put as jest.Mock).mockRejectedValue({
        response: {
          data: {
            detail: 'Invalid configuration',
          },
        },
      });
      (useAuthStore.getState as jest.Mock).mockReturnValue({ token: 'token', login: jest.fn() });

      await useConfigStore.getState().updateSettings({ username: 'x' });

      expect(useConfigStore.getState().error).toBe('Invalid configuration');
      expect(mockShowNotification).toHaveBeenCalledWith(
        'Failed to update settings: Invalid configuration',
        'error'
      );
      consoleSpy.mockRestore();
    });

    it('should handle API error with object detail', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      (api.put as jest.Mock).mockRejectedValue({
        response: {
          data: {
            detail: { code: 'ERR001', field: 'email' },
          },
        },
      });
      (useAuthStore.getState as jest.Mock).mockReturnValue({ token: 'token', login: jest.fn() });

      await useConfigStore.getState().updateSettings({ username: 'x' });

      expect(useConfigStore.getState().error).toBe(JSON.stringify({ code: 'ERR001', field: 'email' }));
      consoleSpy.mockRestore();
    });

    it('should handle API error with message only', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      (api.put as jest.Mock).mockRejectedValue(new Error('Connection failed'));
      (useAuthStore.getState as jest.Mock).mockReturnValue({ token: 'token', login: jest.fn() });

      await useConfigStore.getState().updateSettings({ username: 'x' });

      expect(useConfigStore.getState().error).toBe('Connection failed');
      expect(mockShowNotification).toHaveBeenCalledWith(
        'Failed to update settings: Connection failed',
        'error'
      );
      consoleSpy.mockRestore();
    });

    it('should handle API error without detail or message', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      (api.put as jest.Mock).mockRejectedValue({});
      (useAuthStore.getState as jest.Mock).mockReturnValue({ token: 'token', login: jest.fn() });

      await useConfigStore.getState().updateSettings({ username: 'x' });

      expect(useConfigStore.getState().error).toBe('Failed to update settings');
      consoleSpy.mockRestore();
    });
  });

  describe('deleteKey', () => {
    it('should call API and update stores', async () => {
      const mockResponse = { data: { username: 'test' } };
      (api.delete as jest.Mock).mockResolvedValue(mockResponse);
      (useAuthStore.getState as jest.Mock).mockReturnValue({ token: 'token', login: jest.fn() });

      await useConfigStore.getState().deleteKey('binance');

      expect(api.delete).toHaveBeenCalledWith('/settings/keys/binance');
      expect(useConfigStore.getState().settings).toEqual(mockResponse.data);
      expect(useAuthStore.getState().login).toHaveBeenCalled();
      expect(mockShowNotification).toHaveBeenCalledWith('Keys for binance removed successfully!', 'success');
    });

    it('should handle API error with detail', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      (api.delete as jest.Mock).mockRejectedValue({
        response: { data: { detail: 'Key not found' } },
      });
      (useAuthStore.getState as jest.Mock).mockReturnValue({ token: 'token', login: jest.fn() });

      await useConfigStore.getState().deleteKey('binance');

      expect(useConfigStore.getState().error).toBe('Key not found');
      expect(mockShowNotification).toHaveBeenCalledWith(
        'Failed to delete key: Key not found',
        'error'
      );
      consoleSpy.mockRestore();
    });

    it('should handle API error without detail', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      (api.delete as jest.Mock).mockRejectedValue(new Error('Network error'));
      (useAuthStore.getState as jest.Mock).mockReturnValue({ token: 'token', login: jest.fn() });

      await useConfigStore.getState().deleteKey('binance');

      expect(useConfigStore.getState().error).toBe('Failed to delete key');
      expect(mockShowNotification).toHaveBeenCalledWith(
        'Failed to delete key: Network error',
        'error'
      );
      consoleSpy.mockRestore();
    });
  });

  describe('fetchSupportedExchanges', () => {
    it('should call API and update state', async () => {
      const mockExchanges = ['binance', 'bybit'];
      (api.get as jest.Mock).mockResolvedValue({ data: mockExchanges });

      await useConfigStore.getState().fetchSupportedExchanges();

      expect(api.get).toHaveBeenCalledWith('/settings/exchanges');
      expect(useConfigStore.getState().supportedExchanges).toEqual(mockExchanges);
    });

    it('should handle API error with detail', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      (api.get as jest.Mock).mockRejectedValue({
        response: { data: { detail: 'Service unavailable' } },
      });

      await useConfigStore.getState().fetchSupportedExchanges();

      expect(useConfigStore.getState().error).toBe('Service unavailable');
      consoleSpy.mockRestore();
    });

    it('should handle API error without detail', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      (api.get as jest.Mock).mockRejectedValue(new Error('Network error'));

      await useConfigStore.getState().fetchSupportedExchanges();

      expect(useConfigStore.getState().error).toBe('Failed to fetch supported exchanges');
      consoleSpy.mockRestore();
    });
  });
});
