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
    risk_timer_expires: string | null;
    timer_remaining_minutes: number | null;
    timer_status: string;
    pyramids_reached: boolean;
    pyramid_count: number;
    max_pyramids: number;
    age_minutes: number;
    age_filter_passed: boolean;
  } | null;
  identified_winners: Array<{
    id: string;
    symbol: string;
    unrealized_pnl_usd: number;
  }>;
  required_offset_usd: number;
  total_available_profit: number;
  projected_plan: Array<{
    symbol: string;
    profit_available: number;
    amount_to_close: number;
    partial: boolean;
  }>;
  at_risk_positions: Array<{
    id: string;
    symbol: string;
    unrealized_pnl_percent: number;
    unrealized_pnl_usd: number;
    timer_status: string;
    timer_remaining_minutes: number | null;
    is_eligible: boolean;
    is_selected: boolean;
    risk_blocked: boolean;
  }>;
  recent_actions: Array<{
    id: string;
    timestamp: string | null;
    loser_symbol: string;
    loser_pnl_usd: number;
    winners_count: number;
    action_type: string;
  }>;
  risk_engine_running: boolean;
  config: any;
}

interface RiskStore {
  status: RiskStatus | null;
  loading: boolean;
  error: string | null;
  fetchStatus: (isBackground?: boolean) => Promise<void>;
  runEvaluation: () => Promise<void>;
  blockGroup: (groupId: string) => Promise<void>;
  unblockGroup: (groupId: string) => Promise<void>;
  skipGroup: (groupId: string) => Promise<void>;
}

const useRiskStore = create<RiskStore>((set) => ({
  status: null,
  loading: false,
  error: null,

  fetchStatus: async (isBackground = false) => {
    if (!isBackground) set({ loading: true, error: null });
    try {
      const response = await api.get('/risk/status');

      if (response.data.status === 'not_configured' || response.data.status === 'error') {
        set({ status: null, error: response.data.message, loading: false });
      } else {
        set({ status: response.data, loading: false });
      }
    } catch (error: any) {
      if (!isBackground) set({ error: error.response?.data?.detail || 'Failed to fetch risk status', loading: false });
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