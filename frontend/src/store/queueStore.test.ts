import useQueueStore from './queueStore';
import api from '../services/api';

// Manual mock for api
jest.mock('../services/api', () => ({
  get: jest.fn(),
  post: jest.fn(),
  delete: jest.fn(),
}));

const mockedApi = api as jest.Mocked<typeof api>;

describe('queueStore', () => {
  beforeEach(() => {
    useQueueStore.setState({
      queuedSignals: [],
      queueHistory: [],
      loading: false,
      error: null,
    });
    jest.clearAllMocks();
  });

  describe('setQueuedSignals', () => {
    test('should set queued signals directly', () => {
      const mockSignals = [{ id: '1', symbol: 'BTC', status: 'queued' }] as any;

      useQueueStore.getState().setQueuedSignals(mockSignals);

      expect(useQueueStore.getState().queuedSignals).toEqual(mockSignals);
    });
  });

  describe('fetchQueuedSignals', () => {
    test('success', async () => {
      const mockSignals = [{ id: '1', symbol: 'BTC', status: 'queued' }];
      mockedApi.get.mockResolvedValue({ data: mockSignals });

      await useQueueStore.getState().fetchQueuedSignals();

      expect(mockedApi.get).toHaveBeenCalledWith('/queue/');
      expect(useQueueStore.getState().queuedSignals).toEqual(mockSignals);
      expect(useQueueStore.getState().loading).toBe(false);
      expect(useQueueStore.getState().error).toBe(null);
    });

    test('sets loading when not background', async () => {
      mockedApi.get.mockImplementation(() => new Promise((resolve) => {
        setTimeout(() => resolve({ data: [] }), 50);
      }));

      const promise = useQueueStore.getState().fetchQueuedSignals(false);

      expect(useQueueStore.getState().loading).toBe(true);

      await promise;
    });

    test('does not set loading when background', async () => {
      mockedApi.get.mockImplementation(() => new Promise((resolve) => {
        setTimeout(() => resolve({ data: [] }), 50);
      }));

      const promise = useQueueStore.getState().fetchQueuedSignals(true);

      expect(useQueueStore.getState().loading).toBe(false);

      await promise;
    });

    test('error', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      mockedApi.get.mockRejectedValue({ response: { data: { detail: 'Network Error' } } });

      await useQueueStore.getState().fetchQueuedSignals();

      expect(useQueueStore.getState().loading).toBe(false);
      expect(useQueueStore.getState().error).toBe('Network Error');
      consoleSpy.mockRestore();
    });

    test('error without detail', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      mockedApi.get.mockRejectedValue(new Error('Network error'));

      await useQueueStore.getState().fetchQueuedSignals();

      expect(useQueueStore.getState().error).toBe('Failed to fetch queued signals');
      consoleSpy.mockRestore();
    });

    test('does not set error on background fetch failure', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      mockedApi.get.mockRejectedValue(new Error('Network error'));

      await useQueueStore.getState().fetchQueuedSignals(true);

      expect(useQueueStore.getState().error).toBeNull();
      consoleSpy.mockRestore();
    });

    test('deduplicates concurrent calls', async () => {
      mockedApi.get.mockImplementation(() => new Promise((resolve) => {
        setTimeout(() => resolve({ data: [] }), 50);
      }));

      const promise1 = useQueueStore.getState().fetchQueuedSignals();
      const promise2 = useQueueStore.getState().fetchQueuedSignals();

      await Promise.all([promise1, promise2]);

      expect(mockedApi.get).toHaveBeenCalledTimes(1);
    });
  });

  describe('fetchQueueHistory', () => {
    test('success', async () => {
      const mockHistory = [{ id: '1', symbol: 'BTC', status: 'promoted' }];
      mockedApi.get.mockResolvedValue({ data: mockHistory });

      await useQueueStore.getState().fetchQueueHistory();

      expect(mockedApi.get).toHaveBeenCalledWith('/queue/history');
      expect(useQueueStore.getState().queueHistory).toEqual(mockHistory);
      expect(useQueueStore.getState().loading).toBe(false);
    });

    test('sets loading when not background', async () => {
      mockedApi.get.mockImplementation(() => new Promise((resolve) => {
        setTimeout(() => resolve({ data: [] }), 50);
      }));

      const promise = useQueueStore.getState().fetchQueueHistory(false);

      expect(useQueueStore.getState().loading).toBe(true);

      await promise;
    });

    test('does not set loading when background', async () => {
      mockedApi.get.mockImplementation(() => new Promise((resolve) => {
        setTimeout(() => resolve({ data: [] }), 50);
      }));

      const promise = useQueueStore.getState().fetchQueueHistory(true);

      expect(useQueueStore.getState().loading).toBe(false);

      await promise;
    });

    test('error', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      mockedApi.get.mockRejectedValue({ response: { data: { detail: 'History Error' } } });

      await useQueueStore.getState().fetchQueueHistory();

      expect(useQueueStore.getState().error).toBe('History Error');
      consoleSpy.mockRestore();
    });

    test('error without detail', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      mockedApi.get.mockRejectedValue(new Error('Network error'));

      await useQueueStore.getState().fetchQueueHistory();

      expect(useQueueStore.getState().error).toBe('Failed to fetch queue history');
      consoleSpy.mockRestore();
    });

    test('does not set error on background fetch failure', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      mockedApi.get.mockRejectedValue(new Error('Network error'));

      await useQueueStore.getState().fetchQueueHistory(true);

      expect(useQueueStore.getState().error).toBeNull();
      consoleSpy.mockRestore();
    });

    test('deduplicates concurrent calls', async () => {
      mockedApi.get.mockImplementation(() => new Promise((resolve) => {
        setTimeout(() => resolve({ data: [] }), 50);
      }));

      const promise1 = useQueueStore.getState().fetchQueueHistory();
      const promise2 = useQueueStore.getState().fetchQueueHistory();

      await Promise.all([promise1, promise2]);

      expect(mockedApi.get).toHaveBeenCalledTimes(1);
    });
  });

  describe('promoteSignal', () => {
    test('success', async () => {
      useQueueStore.setState({
        queuedSignals: [{ id: '1', symbol: 'BTC', status: 'queued' } as any],
      });

      mockedApi.post.mockResolvedValue({});
      mockedApi.get.mockResolvedValue({ data: [] });

      await useQueueStore.getState().promoteSignal('1');

      expect(mockedApi.post).toHaveBeenCalledWith('/queue/1/promote');
      expect(mockedApi.get).toHaveBeenCalledWith('/queue/');
    });

    test('error with detail', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      mockedApi.post.mockRejectedValue({
        response: { data: { detail: 'Cannot promote signal' } },
      });

      await useQueueStore.getState().promoteSignal('1');

      expect(useQueueStore.getState().error).toBe('Cannot promote signal');
      expect(useQueueStore.getState().loading).toBe(false);
      consoleSpy.mockRestore();
    });

    test('error without detail', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      mockedApi.post.mockRejectedValue(new Error('Network error'));

      await useQueueStore.getState().promoteSignal('1');

      expect(useQueueStore.getState().error).toBe('Failed to promote signal');
      consoleSpy.mockRestore();
    });
  });

  describe('removeSignal', () => {
    test('success', async () => {
      useQueueStore.setState({
        queuedSignals: [{ id: '1', symbol: 'BTC', status: 'queued' } as any],
      });

      mockedApi.delete.mockResolvedValue({});
      mockedApi.get.mockResolvedValue({ data: [] });

      await useQueueStore.getState().removeSignal('1');

      expect(mockedApi.delete).toHaveBeenCalledWith('/queue/1');
      expect(mockedApi.get).toHaveBeenCalledWith('/queue/');
      expect(useQueueStore.getState().queuedSignals).toHaveLength(0);
    });

    test('error with detail', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      mockedApi.delete.mockRejectedValue({
        response: { data: { detail: 'Cannot remove signal' } },
      });

      await useQueueStore.getState().removeSignal('1');

      expect(useQueueStore.getState().error).toBe('Cannot remove signal');
      expect(useQueueStore.getState().loading).toBe(false);
      consoleSpy.mockRestore();
    });

    test('error without detail', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      mockedApi.delete.mockRejectedValue(new Error('Network error'));

      await useQueueStore.getState().removeSignal('1');

      expect(useQueueStore.getState().error).toBe('Failed to remove signal');
      consoleSpy.mockRestore();
    });
  });
});