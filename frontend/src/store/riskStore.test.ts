import useRiskStore from './riskStore';
import api from '../services/api';

jest.mock('../services/api');

const mockApi = api as jest.Mocked<typeof api>;

describe('riskStore', () => {
  beforeEach(() => {
    useRiskStore.setState({
      status: null,
      loading: false,
      error: null,
    });
    jest.clearAllMocks();
  });

  describe('fetchStatus', () => {
    it('should call API and update state', async () => {
      const mockStatus = {
        identified_loser: null,
        identified_winners: [],
        required_offset_usd: 0,
        risk_engine_running: true,
        config: {},
      };
      mockApi.get.mockResolvedValue({ data: mockStatus });

      await useRiskStore.getState().fetchStatus();

      expect(mockApi.get).toHaveBeenCalledWith('/risk/status');
      expect(useRiskStore.getState().status).toEqual(mockStatus);
      expect(useRiskStore.getState().loading).toBe(false);
    });

    it('should set loading true when not background', async () => {
      mockApi.get.mockImplementation(() => new Promise((resolve) => {
        setTimeout(() => resolve({ data: {} }), 50);
      }));

      const promise = useRiskStore.getState().fetchStatus(false);

      // Check loading state immediately
      expect(useRiskStore.getState().loading).toBe(true);

      await promise;
    });

    it('should not set loading when background fetch', async () => {
      mockApi.get.mockImplementation(() => new Promise((resolve) => {
        setTimeout(() => resolve({ data: {} }), 50);
      }));

      const promise = useRiskStore.getState().fetchStatus(true);

      // Loading should not be set for background fetch
      expect(useRiskStore.getState().loading).toBe(false);

      await promise;
    });

    it('should handle not_configured status', async () => {
      mockApi.get.mockResolvedValue({
        data: {
          status: 'not_configured',
          message: 'Risk engine not configured'
        }
      });

      await useRiskStore.getState().fetchStatus();

      expect(useRiskStore.getState().status).toBeNull();
      expect(useRiskStore.getState().error).toBe('Risk engine not configured');
    });

    it('should handle error status', async () => {
      mockApi.get.mockResolvedValue({
        data: {
          status: 'error',
          message: 'An error occurred'
        }
      });

      await useRiskStore.getState().fetchStatus();

      expect(useRiskStore.getState().status).toBeNull();
      expect(useRiskStore.getState().error).toBe('An error occurred');
    });

    it('should handle API error', async () => {
      mockApi.get.mockRejectedValue({
        response: { data: { detail: 'API Error' } }
      });

      await useRiskStore.getState().fetchStatus();

      expect(useRiskStore.getState().error).toBe('API Error');
      expect(useRiskStore.getState().loading).toBe(false);
    });

    it('should handle API error without detail', async () => {
      mockApi.get.mockRejectedValue(new Error('Network error'));

      await useRiskStore.getState().fetchStatus();

      expect(useRiskStore.getState().error).toBe('Failed to fetch risk status');
    });

    it('should not set error on background fetch failure', async () => {
      mockApi.get.mockRejectedValue(new Error('Network error'));

      await useRiskStore.getState().fetchStatus(true);

      expect(useRiskStore.getState().error).toBeNull();
    });

    it('should deduplicate concurrent calls', async () => {
      mockApi.get.mockImplementation(() => new Promise((resolve) => {
        setTimeout(() => resolve({ data: { risk_engine_running: true } }), 50);
      }));

      // Start two concurrent calls
      const promise1 = useRiskStore.getState().fetchStatus();
      const promise2 = useRiskStore.getState().fetchStatus();

      await Promise.all([promise1, promise2]);

      // Should only have called API once
      expect(mockApi.get).toHaveBeenCalledTimes(1);
    });
  });

  describe('runEvaluation', () => {
    it('should call API and refresh status', async () => {
      mockApi.post.mockResolvedValue({});
      mockApi.get.mockResolvedValue({ data: {} });

      await useRiskStore.getState().runEvaluation();

      expect(mockApi.post).toHaveBeenCalledWith('/risk/run-evaluation');
      expect(mockApi.get).toHaveBeenCalledWith('/risk/status');
    });

    it('should handle API error', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      mockApi.post.mockRejectedValue({
        response: { data: { detail: 'Evaluation failed' } }
      });

      await useRiskStore.getState().runEvaluation();

      expect(useRiskStore.getState().error).toBe('Evaluation failed');
      consoleSpy.mockRestore();
    });

    it('should handle API error without detail', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      mockApi.post.mockRejectedValue(new Error('Network error'));

      await useRiskStore.getState().runEvaluation();

      expect(useRiskStore.getState().error).toBe('Failed to run evaluation');
      consoleSpy.mockRestore();
    });
  });

  describe('blockGroup', () => {
    it('should call API and refresh status', async () => {
      mockApi.post.mockResolvedValue({});
      mockApi.get.mockResolvedValue({ data: {} });

      await useRiskStore.getState().blockGroup('123');

      expect(mockApi.post).toHaveBeenCalledWith('/risk/123/block');
      expect(mockApi.get).toHaveBeenCalledWith('/risk/status');
    });

    it('should handle API error', async () => {
      mockApi.post.mockRejectedValue({
        response: { data: { detail: 'Block failed' } }
      });

      await useRiskStore.getState().blockGroup('123');

      expect(useRiskStore.getState().error).toBe('Block failed');
    });

    it('should handle API error without detail', async () => {
      mockApi.post.mockRejectedValue(new Error('Network error'));

      await useRiskStore.getState().blockGroup('123');

      expect(useRiskStore.getState().error).toBe('Failed to block group');
    });
  });

  describe('unblockGroup', () => {
    it('should call API and refresh status', async () => {
      mockApi.post.mockResolvedValue({});
      mockApi.get.mockResolvedValue({ data: {} });

      await useRiskStore.getState().unblockGroup('456');

      expect(mockApi.post).toHaveBeenCalledWith('/risk/456/unblock');
      expect(mockApi.get).toHaveBeenCalledWith('/risk/status');
    });

    it('should handle API error', async () => {
      mockApi.post.mockRejectedValue({
        response: { data: { detail: 'Unblock failed' } }
      });

      await useRiskStore.getState().unblockGroup('456');

      expect(useRiskStore.getState().error).toBe('Unblock failed');
    });

    it('should handle API error without detail', async () => {
      mockApi.post.mockRejectedValue(new Error('Network error'));

      await useRiskStore.getState().unblockGroup('456');

      expect(useRiskStore.getState().error).toBe('Failed to unblock group');
    });
  });

  describe('skipGroup', () => {
    it('should call API and refresh status', async () => {
      mockApi.post.mockResolvedValue({});
      mockApi.get.mockResolvedValue({ data: {} });

      await useRiskStore.getState().skipGroup('789');

      expect(mockApi.post).toHaveBeenCalledWith('/risk/789/skip');
      expect(mockApi.get).toHaveBeenCalledWith('/risk/status');
    });

    it('should handle API error', async () => {
      mockApi.post.mockRejectedValue({
        response: { data: { detail: 'Skip failed' } }
      });

      await useRiskStore.getState().skipGroup('789');

      expect(useRiskStore.getState().error).toBe('Skip failed');
    });

    it('should handle API error without detail', async () => {
      mockApi.post.mockRejectedValue(new Error('Network error'));

      await useRiskStore.getState().skipGroup('789');

      expect(useRiskStore.getState().error).toBe('Failed to skip group');
    });
  });

  describe('forceStop', () => {
    it('should call API and refresh status', async () => {
      mockApi.post.mockResolvedValue({});
      mockApi.get.mockResolvedValue({ data: {} });

      await useRiskStore.getState().forceStop();

      expect(mockApi.post).toHaveBeenCalledWith('/risk/force-stop');
      expect(mockApi.get).toHaveBeenCalledWith('/risk/status');
    });

    it('should handle API error', async () => {
      mockApi.post.mockRejectedValue({
        response: { data: { detail: 'Force stop failed' } }
      });

      await useRiskStore.getState().forceStop();

      expect(useRiskStore.getState().error).toBe('Force stop failed');
    });

    it('should handle API error without detail', async () => {
      mockApi.post.mockRejectedValue(new Error('Network error'));

      await useRiskStore.getState().forceStop();

      expect(useRiskStore.getState().error).toBe('Failed to force stop engine');
    });
  });

  describe('forceStart', () => {
    it('should call API and refresh status', async () => {
      mockApi.post.mockResolvedValue({});
      mockApi.get.mockResolvedValue({ data: {} });

      await useRiskStore.getState().forceStart();

      expect(mockApi.post).toHaveBeenCalledWith('/risk/force-start');
      expect(mockApi.get).toHaveBeenCalledWith('/risk/status');
    });

    it('should handle API error', async () => {
      mockApi.post.mockRejectedValue({
        response: { data: { detail: 'Force start failed' } }
      });

      await useRiskStore.getState().forceStart();

      expect(useRiskStore.getState().error).toBe('Force start failed');
    });

    it('should handle API error without detail', async () => {
      mockApi.post.mockRejectedValue(new Error('Network error'));

      await useRiskStore.getState().forceStart();

      expect(useRiskStore.getState().error).toBe('Failed to force start engine');
    });
  });

  describe('syncExchange', () => {
    it('should call API and refresh status', async () => {
      mockApi.post.mockResolvedValue({});
      mockApi.get.mockResolvedValue({ data: {} });

      await useRiskStore.getState().syncExchange();

      expect(mockApi.post).toHaveBeenCalledWith('/risk/sync-exchange');
      expect(mockApi.get).toHaveBeenCalledWith('/risk/status');
    });

    it('should handle API error', async () => {
      mockApi.post.mockRejectedValue({
        response: { data: { detail: 'Sync failed' } }
      });

      await useRiskStore.getState().syncExchange();

      expect(useRiskStore.getState().error).toBe('Sync failed');
    });

    it('should handle API error without detail', async () => {
      mockApi.post.mockRejectedValue(new Error('Network error'));

      await useRiskStore.getState().syncExchange();

      expect(useRiskStore.getState().error).toBe('Failed to sync with exchange');
    });
  });
});