import usePositionsStore from './positionsStore';
import useNotificationStore from './notificationStore';
import api from '../services/api';

jest.mock('../services/api');
jest.mock('./notificationStore');

const mockApi = api as jest.Mocked<typeof api>;

describe('positionsStore', () => {
  const mockShowNotification = jest.fn();

  beforeEach(() => {
    usePositionsStore.setState({
      positions: [],
      positionHistory: [],
      positionHistoryTotal: 0,
      loading: false,
      error: null,
    });
    jest.clearAllMocks();
    (useNotificationStore.getState as jest.Mock).mockReturnValue({
      showNotification: mockShowNotification,
    });
  });

  describe('setPositions', () => {
    it('should set positions directly', () => {
      const mockPositions = [
        { id: '1', symbol: 'BTC/USDT', status: 'active' },
      ] as any;

      usePositionsStore.getState().setPositions(mockPositions);

      expect(usePositionsStore.getState().positions).toEqual(mockPositions);
    });
  });

  describe('fetchPositions', () => {
    it('should fetch positions from API', async () => {
      const mockPositions = [
        { id: '1', symbol: 'BTC/USDT', status: 'active' },
        { id: '2', symbol: 'ETH/USDT', status: 'active' },
      ];
      mockApi.get.mockResolvedValue({ data: mockPositions });

      await usePositionsStore.getState().fetchPositions();

      expect(mockApi.get).toHaveBeenCalledWith('/positions/active');
      expect(usePositionsStore.getState().positions).toEqual(mockPositions);
      expect(usePositionsStore.getState().loading).toBe(false);
    });

    it('should set loading true when not background', async () => {
      mockApi.get.mockImplementation(() => new Promise((resolve) => {
        setTimeout(() => resolve({ data: [] }), 50);
      }));

      const promise = usePositionsStore.getState().fetchPositions(false);

      expect(usePositionsStore.getState().loading).toBe(true);

      await promise;
    });

    it('should not set loading when background fetch', async () => {
      mockApi.get.mockImplementation(() => new Promise((resolve) => {
        setTimeout(() => resolve({ data: [] }), 50);
      }));

      const promise = usePositionsStore.getState().fetchPositions(true);

      expect(usePositionsStore.getState().loading).toBe(false);

      await promise;
    });

    it('should handle API error', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      mockApi.get.mockRejectedValue({
        response: { data: { detail: 'Failed to fetch' } },
      });

      await usePositionsStore.getState().fetchPositions();

      expect(usePositionsStore.getState().error).toBe('Failed to fetch');
      expect(usePositionsStore.getState().loading).toBe(false);
      consoleSpy.mockRestore();
    });

    it('should handle API error without detail', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      mockApi.get.mockRejectedValue(new Error('Network error'));

      await usePositionsStore.getState().fetchPositions();

      expect(usePositionsStore.getState().error).toBe('Failed to fetch positions');
      consoleSpy.mockRestore();
    });

    it('should not set error on background fetch failure', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      mockApi.get.mockRejectedValue(new Error('Network error'));

      await usePositionsStore.getState().fetchPositions(true);

      expect(usePositionsStore.getState().error).toBeNull();
      consoleSpy.mockRestore();
    });

    it('should deduplicate concurrent calls', async () => {
      mockApi.get.mockImplementation(() => new Promise((resolve) => {
        setTimeout(() => resolve({ data: [] }), 50);
      }));

      const promise1 = usePositionsStore.getState().fetchPositions();
      const promise2 = usePositionsStore.getState().fetchPositions();

      await Promise.all([promise1, promise2]);

      expect(mockApi.get).toHaveBeenCalledTimes(1);
    });
  });

  describe('fetchPositionHistory', () => {
    it('should fetch position history from API', async () => {
      const mockHistory = {
        items: [
          { id: '1', symbol: 'BTC/USDT', status: 'closed' },
        ],
        total: 1,
        limit: 100,
        offset: 0,
      };
      mockApi.get.mockResolvedValue({ data: mockHistory });

      await usePositionsStore.getState().fetchPositionHistory();

      expect(mockApi.get).toHaveBeenCalledWith('/positions/history', {
        params: { limit: 100, offset: 0 },
      });
      expect(usePositionsStore.getState().positionHistory).toEqual(mockHistory.items);
      expect(usePositionsStore.getState().positionHistoryTotal).toBe(1);
    });

    it('should use provided limit and offset', async () => {
      mockApi.get.mockResolvedValue({
        data: { items: [], total: 0, limit: 50, offset: 100 },
      });

      await usePositionsStore.getState().fetchPositionHistory(false, 50, 100);

      expect(mockApi.get).toHaveBeenCalledWith('/positions/history', {
        params: { limit: 50, offset: 100 },
      });
    });

    it('should set loading true when not background', async () => {
      mockApi.get.mockImplementation(() => new Promise((resolve) => {
        setTimeout(() => resolve({ data: { items: [], total: 0 } }), 50);
      }));

      const promise = usePositionsStore.getState().fetchPositionHistory(false);

      expect(usePositionsStore.getState().loading).toBe(true);

      await promise;
    });

    it('should not set loading when background fetch', async () => {
      mockApi.get.mockImplementation(() => new Promise((resolve) => {
        setTimeout(() => resolve({ data: { items: [], total: 0 } }), 50);
      }));

      const promise = usePositionsStore.getState().fetchPositionHistory(true);

      expect(usePositionsStore.getState().loading).toBe(false);

      await promise;
    });

    it('should handle API error', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      mockApi.get.mockRejectedValue({
        response: { data: { detail: 'History unavailable' } },
      });

      await usePositionsStore.getState().fetchPositionHistory();

      expect(usePositionsStore.getState().error).toBe('History unavailable');
      consoleSpy.mockRestore();
    });

    it('should handle API error without detail', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      mockApi.get.mockRejectedValue(new Error('Network error'));

      await usePositionsStore.getState().fetchPositionHistory();

      expect(usePositionsStore.getState().error).toBe('Failed to fetch position history');
      consoleSpy.mockRestore();
    });

    it('should not set error on background fetch failure', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      mockApi.get.mockRejectedValue(new Error('Network error'));

      await usePositionsStore.getState().fetchPositionHistory(true);

      expect(usePositionsStore.getState().error).toBeNull();
      consoleSpy.mockRestore();
    });
  });

  describe('closePosition', () => {
    it('should close position and refresh', async () => {
      mockApi.post.mockResolvedValue({});
      mockApi.get.mockResolvedValue({ data: [] });

      await usePositionsStore.getState().closePosition('group-123');

      expect(mockApi.post).toHaveBeenCalledWith('/positions/group-123/close');
      expect(mockShowNotification).toHaveBeenCalledWith('Position close initiated.', 'success');
      expect(mockApi.get).toHaveBeenCalledWith('/positions/active');
    });

    it('should handle API error with detail', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      mockApi.post.mockRejectedValue({
        response: { data: { detail: 'Cannot close position' } },
      });

      await usePositionsStore.getState().closePosition('group-123');

      expect(mockShowNotification).toHaveBeenCalledWith('Cannot close position', 'error');
      consoleSpy.mockRestore();
    });

    it('should handle API error without detail', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      mockApi.post.mockRejectedValue(new Error('Network error'));

      await usePositionsStore.getState().closePosition('group-123');

      expect(mockShowNotification).toHaveBeenCalledWith('Failed to force close position', 'error');
      consoleSpy.mockRestore();
    });
  });
});
