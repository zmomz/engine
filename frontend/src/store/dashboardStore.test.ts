import useDashboardStore, { startDashboardPolling, stopDashboardPolling } from './dashboardStore';
import api from '../services/api';

jest.mock('../services/api');

const mockApi = api as jest.Mocked<typeof api>;

describe('dashboardStore', () => {
  beforeEach(() => {
    useDashboardStore.setState({
      data: null,
      loading: false,
      error: null,
    });
    jest.clearAllMocks();
    jest.useFakeTimers();
  });

  afterEach(() => {
    stopDashboardPolling();
    jest.useRealTimers();
  });

  describe('fetchDashboardData', () => {
    it('should fetch dashboard data from API', async () => {
      const mockData = {
        live_dashboard: {
          total_active_position_groups: 5,
          queued_signals_count: 2,
          total_pnl_usd: 1000,
        },
        timestamp: '2024-01-01T00:00:00Z',
      };
      mockApi.get.mockResolvedValue({ data: mockData });

      await useDashboardStore.getState().fetchDashboardData();

      expect(mockApi.get).toHaveBeenCalledWith('/dashboard/analytics');
      expect(useDashboardStore.getState().data).toEqual(mockData);
      expect(useDashboardStore.getState().loading).toBe(false);
    });

    it('should set loading true when not background', async () => {
      mockApi.get.mockImplementation(() => new Promise((resolve) => {
        setTimeout(() => resolve({ data: {} }), 50);
      }));

      const promise = useDashboardStore.getState().fetchDashboardData(false);

      expect(useDashboardStore.getState().loading).toBe(true);

      jest.advanceTimersByTime(50);
      await promise;
    });

    it('should not set loading when background fetch', async () => {
      mockApi.get.mockImplementation(() => new Promise((resolve) => {
        setTimeout(() => resolve({ data: {} }), 50);
      }));

      const promise = useDashboardStore.getState().fetchDashboardData(true);

      expect(useDashboardStore.getState().loading).toBe(false);

      jest.advanceTimersByTime(50);
      await promise;
    });

    it('should handle API error', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      mockApi.get.mockRejectedValue({
        response: { data: { detail: 'Server error' } },
      });

      await useDashboardStore.getState().fetchDashboardData();

      expect(useDashboardStore.getState().error).toBe('Server error');
      expect(useDashboardStore.getState().loading).toBe(false);
      consoleSpy.mockRestore();
    });

    it('should handle API error without detail', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      mockApi.get.mockRejectedValue(new Error('Network error'));

      await useDashboardStore.getState().fetchDashboardData();

      expect(useDashboardStore.getState().error).toBe('Failed to fetch dashboard data');
      consoleSpy.mockRestore();
    });

    it('should not set error on background fetch failure', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      mockApi.get.mockRejectedValue(new Error('Network error'));

      await useDashboardStore.getState().fetchDashboardData(true);

      expect(useDashboardStore.getState().error).toBeNull();
      consoleSpy.mockRestore();
    });

    it('should deduplicate concurrent calls', async () => {
      mockApi.get.mockImplementation(() => new Promise((resolve) => {
        setTimeout(() => resolve({ data: {} }), 50);
      }));

      const promise1 = useDashboardStore.getState().fetchDashboardData();
      const promise2 = useDashboardStore.getState().fetchDashboardData();

      jest.advanceTimersByTime(50);
      await Promise.all([promise1, promise2]);

      expect(mockApi.get).toHaveBeenCalledTimes(1);
    });
  });

  describe('polling', () => {
    it('startDashboardPolling should start polling', async () => {
      mockApi.get.mockResolvedValue({ data: {} });

      startDashboardPolling();

      expect(mockApi.get).not.toHaveBeenCalled();

      // First interval tick
      jest.advanceTimersByTime(1000);
      await Promise.resolve();
      expect(mockApi.get).toHaveBeenCalled();
    });

    it('startDashboardPolling should not start multiple intervals', async () => {
      mockApi.get.mockResolvedValue({ data: {} });

      startDashboardPolling();
      startDashboardPolling();
      startDashboardPolling();

      jest.advanceTimersByTime(1000);
      await Promise.resolve();

      // Should only be 1 call despite multiple startDashboardPolling calls
      expect(mockApi.get).toHaveBeenCalledTimes(1);
    });

    it('stopDashboardPolling should stop polling', async () => {
      mockApi.get.mockResolvedValue({ data: {} });

      startDashboardPolling();

      jest.advanceTimersByTime(1000);
      await Promise.resolve();
      const callCount = mockApi.get.mock.calls.length;

      stopDashboardPolling();

      jest.advanceTimersByTime(5000);
      await Promise.resolve();

      // No additional calls after stop
      expect(mockApi.get).toHaveBeenCalledTimes(callCount);
    });

    it('stopDashboardPolling should be safe to call when not polling', () => {
      expect(() => stopDashboardPolling()).not.toThrow();
    });
  });
});
