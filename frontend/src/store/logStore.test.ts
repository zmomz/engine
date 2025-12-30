import { act } from 'react';
import useLogStore from './logStore';
import api from '../services/api';

// Mock API
jest.mock('../services/api');

describe('logStore', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    useLogStore.setState({ logs: [], loading: false, error: null });
  });

  test('fetchLogs success', async () => {
    (api.get as jest.Mock).mockResolvedValue({
      data: { logs: ['line 1', 'line 2'] }
    });

    await act(async () => {
        await useLogStore.getState().fetchLogs(100, 'INFO');
    });

    const state = useLogStore.getState();
    expect(state.logs).toEqual(['line 1', 'line 2']);
    expect(state.loading).toBe(false);
    expect(state.error).toBeNull();
    expect(api.get).toHaveBeenCalledWith('/logs', { params: { lines: 100, level: 'INFO' } });
  });

  test('fetchLogs error', async () => {
    (api.get as jest.Mock).mockRejectedValue({
      response: { data: { detail: 'API Error' } }
    });

    await act(async () => {
        await useLogStore.getState().fetchLogs();
    });

    const state = useLogStore.getState();
    expect(state.logs).toEqual([]);
    expect(state.loading).toBe(false);
    expect(state.error).toBe('API Error');
  });
});
