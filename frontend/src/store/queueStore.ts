import { create } from 'zustand';
import axios from 'axios';

interface QueuedSignal {
  id: string;
  symbol: string;
  side: string;
  signal_type: string;
  priority_score: number;
  created_at: string;
  // Add other relevant fields from your QueuedSignalSchema
}

interface QueueState {
  queuedSignals: QueuedSignal[];
  loading: boolean;
  error: string | null;
  fetchQueuedSignals: () => Promise<void>;
  promoteSignal: (signalId: string) => Promise<void>;
  removeSignal: (signalId: string) => Promise<void>;
}

const useQueueStore = create<QueueState>((set) => ({
  queuedSignals: [],
  loading: false,
  error: null,

  fetchQueuedSignals: async () => {
    set({ loading: true, error: null });
    try {
      const response = await axios.get<QueuedSignal[]>('/api/v1/queue/');
      set({ queuedSignals: response.data, loading: false });
    } catch (err: any) {
      console.error("Failed to fetch queued signals", err);
      set({ error: err.response?.data?.detail || 'Failed to fetch queued signals', loading: false });
    }
  },

  promoteSignal: async (signalId: string) => {
    set({ loading: true, error: null });
    try {
      await axios.post(`/api/v1/queue/${signalId}/promote`);
      // Refresh the list after promoting
      await useQueueStore.getState().fetchQueuedSignals();
    } catch (err: any) {
      console.error("Failed to promote signal", err);
      set({ error: err.response?.data?.detail || 'Failed to promote signal', loading: false });
    }
  },

  removeSignal: async (signalId: string) => {
    set({ loading: true, error: null });
    try {
      await axios.delete(`/api/v1/queue/${signalId}`);
      // Refresh the list after removing
      await useQueueStore.getState().fetchQueuedSignals();
    } catch (err: any) {
      console.error("Failed to remove signal", err);
      set({ error: err.response?.data?.detail || 'Failed to remove signal', loading: false });
    }
  },
}));

export default useQueueStore;