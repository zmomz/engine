import { create } from 'zustand';
import api from '../services/api';

interface LogStore {
  logs: string[];
  loading: boolean;
  error: string | null;
  fetchLogs: (lines?: number, level?: string) => Promise<void>;
}

const useLogStore = create<LogStore>((set) => ({
  logs: [],
  loading: false,
  error: null,

  fetchLogs: async (lines = 100, level) => {
    set({ loading: true, error: null });
    try {
      const params: any = { lines };
      if (level && level !== 'all') {
        params.level = level.toUpperCase();
      }
      
      const response = await api.get('/logs', { params });
      set({ logs: response.data.logs, loading: false });
    } catch (error: any) {
      set({ error: error.response?.data?.detail || 'Failed to fetch logs', loading: false });
    }
  },
}));

export default useLogStore;
