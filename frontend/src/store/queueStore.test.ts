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
    useQueueStore.setState({ queuedSignals: [], loading: false, error: null });
    jest.clearAllMocks();
  });

  test('fetchQueuedSignals success', async () => {
    const mockSignals = [{ id: '1', symbol: 'BTC', status: 'queued' }];
    mockedApi.get.mockResolvedValue({ data: mockSignals });

    await useQueueStore.getState().fetchQueuedSignals();

    expect(useQueueStore.getState().queuedSignals).toEqual(mockSignals);
    expect(useQueueStore.getState().loading).toBe(false);
    expect(useQueueStore.getState().error).toBe(null);
  });

  test('fetchQueuedSignals error', async () => {
    mockedApi.get.mockRejectedValue({ response: { data: { detail: 'Network Error' } } });

    await useQueueStore.getState().fetchQueuedSignals();

    expect(useQueueStore.getState().loading).toBe(false);
    expect(useQueueStore.getState().error).toBe('Network Error');
  });

  test('removeSignal success', async () => {
    // Setup initial state
    useQueueStore.setState({ 
        queuedSignals: [{ id: '1', symbol: 'BTC', status: 'queued', side: 'long', signal_type: 'manual', priority_score: 10, queued_at: 'now' } as any] 
    });
    
    mockedApi.delete.mockResolvedValue({});
    mockedApi.get.mockResolvedValue({ data: [] }); // Expect re-fetch

    await useQueueStore.getState().removeSignal('1');

    expect(mockedApi.delete).toHaveBeenCalledWith('/queue/1');
    expect(mockedApi.get).toHaveBeenCalled(); // Verify refetch
    expect(useQueueStore.getState().queuedSignals).toHaveLength(0);
  });

  test('promoteSignal success', async () => {
    // Setup initial state
    useQueueStore.setState({ 
        queuedSignals: [{ id: '1', symbol: 'BTC', status: 'queued', side: 'long', signal_type: 'manual', priority_score: 10, queued_at: 'now' } as any] 
    });

    mockedApi.post.mockResolvedValue({});
    mockedApi.get.mockResolvedValue({ data: [] }); // Expect re-fetch returning empty (simulating promoted moved out)

    await useQueueStore.getState().promoteSignal('1');

    expect(mockedApi.post).toHaveBeenCalledWith('/queue/1/promote');
    expect(mockedApi.get).toHaveBeenCalled(); // Verify refetch
  });
});