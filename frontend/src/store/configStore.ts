import { create } from 'zustand';
import api from '../services/api';
import useAuthStore from './authStore';

export interface DCALevelConfig {
  gap_percent: number;
  weight_percent: number;
  tp_percent: number;
}

export interface DCAGridConfig extends Array<DCALevelConfig> {}

export interface RiskEngineConfig {
  max_open_positions_global: number;
  max_open_positions_per_symbol: number;
  max_total_exposure_usd: number;
  max_daily_loss_usd: number;
  loss_threshold_percent: number;
  timer_start_condition: string;
  post_full_wait_minutes: number;
  max_winners_to_combine: number;
  use_trade_age_filter: boolean;
  age_threshold_minutes: number;
  require_full_pyramids: boolean;
  reset_timer_on_replacement: boolean;
  partial_close_enabled: boolean;
  min_close_notional: number;
}

export interface UserSettings {
  id: string;
  username: string;
  email: string;
  exchange: string;
  webhook_secret: string;
  configured_exchanges: string[];
  risk_config: RiskEngineConfig;
  dca_grid_config: DCAGridConfig;
}

interface ConfigState {
  settings: UserSettings | null;
  supportedExchanges: string[];
  loading: boolean;
  error: string | null;
  fetchSettings: () => Promise<void>;
  updateSettings: (updatedSettings: Partial<UserSettings>) => Promise<void>;
  deleteKey: (exchange: string) => Promise<void>;
  fetchSupportedExchanges: () => Promise<void>;
}

const useConfigStore = create<ConfigState>((set) => ({
  settings: null,
  supportedExchanges: [],
  loading: false,
  error: null,

  fetchSettings: async () => {
    set({ loading: true, error: null });
    try {
      // The user object from useAuthStore already contains the current settings
      const currentUser = useAuthStore.getState().user;
      if (currentUser) {
        set({ settings: currentUser, loading: false });
      } else {
        set({ error: 'User not authenticated', loading: false });
      }
    } catch (err: any) {
      console.error("Failed to fetch settings", err);
      set({ error: err.response?.data?.detail || 'Failed to fetch settings', loading: false });
    }
  },

  updateSettings: async (updatedSettings: Partial<UserSettings>) => {
    set({ loading: true, error: null });
    try {
      const response = await api.put<UserSettings>('/settings', updatedSettings);
      set({ settings: response.data, loading: false });
      // Also update the user in the auth store
      useAuthStore.getState().login(useAuthStore.getState().token!, response.data);
      alert('Settings updated successfully!');
    } catch (err: any) {
      console.error("Failed to update settings", err);
      set({ error: err.response?.data?.detail || 'Failed to update settings', loading: false });
      alert(`Failed to update settings: ${err.response?.data?.detail || err.message}`);
    }
  },

  deleteKey: async (exchange: string) => {
    set({ loading: true, error: null });
    try {
      const response = await api.delete<UserSettings>(`/settings/keys/${exchange}`);
      set({ settings: response.data, loading: false });
      // Also update the user in the auth store
      useAuthStore.getState().login(useAuthStore.getState().token!, response.data);
      alert(`Keys for ${exchange} removed successfully!`);
    } catch (err: any) {
      console.error("Failed to delete key", err);
      set({ error: err.response?.data?.detail || 'Failed to delete key', loading: false });
      alert(`Failed to delete key: ${err.response?.data?.detail || err.message}`);
    }
  },

  fetchSupportedExchanges: async () => {

    set({ loading: true, error: null });
    try {
      const response = await api.get<string[]>('/settings/exchanges');
      set({ supportedExchanges: response.data, loading: false });
    } catch (err: any) {
      console.error("Failed to fetch supported exchanges", err);
      set({ error: err.response?.data?.detail || 'Failed to fetch supported exchanges', loading: false });
    }
  },
}));

export default useConfigStore;
