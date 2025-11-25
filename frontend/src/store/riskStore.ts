import { create } from 'zustand';
import api from '../services/api';

interface RiskStatus {
  identified_loser: {
    id: string;
    symbol: string;
    unrealized_pnl_percent: number;
    unrealized_pnl_usd: number;
    risk_blocked: boolean;
    risk_skip_once: boolean;
  } | null;
  identified_winners: Array<{
    id: string;
    symbol: string;
    unrealized_pnl_usd: number;
  }>;
  required_offset_usd: number;
  risk_engine_running: boolean;
  config: any;
}

interface RiskStore {
  status: RiskStatus | null;
  loading: boolean;
  error: string | null;
  fetchStatus: () => Promise<void>;
  runEvaluation: () => Promise<void>;
  blockGroup: (groupId: string) => Promise<void>;
  unblockGroup: (groupId: string) => Promise<void>;
  skipGroup: (groupId: string) => Promise<void>;
}

const useRiskStore = create<RiskStore>((set) => ({
  status: null,
  loading: false,
  error: null,

  fetchStatus: async () => {
    set({ loading: true, error: null });
    try {
      const response = await api.get('/risk/status');
      
      if (response.data.status === 'not_configured' || response.data.status === 'error') {
        set({ status: null, error: response.data.message, loading: false });
      } else {
        set({ status: response.data, loading: false });
      }
    } catch (error: any) {
      set({ error: error.response?.data?.detail || 'Failed to fetch risk status', loading: false });
    }
  },

  runEvaluation: async () => {
    try {
      await api.post('/risk/run-evaluation');
      // Refresh status after run
      useRiskStore.getState().fetchStatus();
    } catch (error: any) {
      console.error('Failed to run evaluation:', error);
      set({ error: error.response?.data?.detail || 'Failed to run evaluation' });
    }
  },

  blockGroup: async (groupId: string) => {
    try {
      await api.post(`/risk/${groupId}/block`);
      useRiskStore.getState().fetchStatus();
    } catch (error: any) {
        set({ error: error.response?.data?.detail || 'Failed to block group' });
    }
  },

  unblockGroup: async (groupId: string) => {
    try {
      await api.post(`/risk/${groupId}/unblock`);
      useRiskStore.getState().fetchStatus();
    } catch (error: any) {
        set({ error: error.response?.data?.detail || 'Failed to unblock group' });
    }
  },

  skipGroup: async (groupId: string) => {
    try {
      await api.post(`/risk/${groupId}/skip`);
      useRiskStore.getState().fetchStatus();
    } catch (error: any) {
        set({ error: error.response?.data?.detail || 'Failed to skip group' });
    }
  },
}));

export default useRiskStore;