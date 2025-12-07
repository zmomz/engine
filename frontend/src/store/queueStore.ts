import { create } from 'zustand';
import api from '../services/api';

interface QueuedSignal {
  id: string;
  user_id: string;
  exchange: string;
  symbol: string;
  timeframe: number;
  side: 'long' | 'short';
  entry_price: number;
  signal_payload: Record<string, any>;
  queued_at: string;
  replacement_count: number;
  priority_score: number;
  is_pyramid_continuation: boolean;
  current_loss_percent: number | null;
  status: 'queued' | 'promoted' | 'cancelled';
  promoted_at: string | null;
  priority_explanation: string | null;
  signal_type?: string; // Keeping this as optional as it's used in frontend but not directly in backend schema
}

interface QueueState {
  queuedSignals: QueuedSignal[];
  loading: boolean;
  error: string | null;
  fetchQueuedSignals: (isBackground?: boolean) => Promise<void>;
  promoteSignal: (signalId: string) => Promise<void>;
  removeSignal: (signalId: string) => Promise<void>;
  setQueuedSignals: (signals: QueuedSignal[]) => void;
  fetchQueueHistory: (isBackground?: boolean) => Promise<void>;
  queueHistory: QueuedSignal[];
}

const useQueueStore = create<QueueState>((set) => ({
  queuedSignals: [],
  queueHistory: [],
  loading: false,
  error: null,

  setQueuedSignals: (signals) => set({ queuedSignals: signals }),

  fetchQueuedSignals: async (isBackground = false) => {
    if (!isBackground) set({ loading: true, error: null });
    try {
      const response = await api.get<QueuedSignal[]>('/queue/');
      set({ queuedSignals: response.data, loading: false });
    } catch (err: any) {
      console.error("Failed to fetch queued signals", err);
      // Only set error if not background, or handle silently
      if (!isBackground) set({ error: err.response?.data?.detail || 'Failed to fetch queued signals', loading: false });
    }
  },

  fetchQueueHistory: async (isBackground = false) => {
    if (!isBackground) set({ loading: true, error: null });
    try {
      const response = await api.get<QueuedSignal[]>('/queue/history');
      set({ queueHistory: response.data, loading: false });
    } catch (err: any) {
      console.error("Failed to fetch queue history", err);
      if (!isBackground) set({ error: err.response?.data?.detail || 'Failed to fetch queue history', loading: false });
    }
  },

  promoteSignal: async (signalId: string) => {
    set({ loading: true, error: null });
    try {
      await api.post(`/queue/${signalId}/promote`);
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
      await api.delete(`/queue/${signalId}`);
      // Refresh the list after removing
      await useQueueStore.getState().fetchQueuedSignals();
    } catch (err: any) {
      console.error("Failed to remove signal", err);
      set({ error: err.response?.data?.detail || 'Failed to remove signal', loading: false });
    }
  },
}));

export default useQueueStore;