import { create } from 'zustand';
import api from '../services/api';
import useAuthStore from './authStore';
import useNotificationStore from './notificationStore';

export interface PriorityRulesConfig {
  priority_rules_enabled: {
    same_pair_timeframe: boolean;
    deepest_loss_percent: boolean;
    highest_replacement: boolean;
    fifo_fallback: boolean;
  };
  priority_order: string[];
}

export interface RiskEngineConfig {
  max_open_positions_global: number;
  max_open_positions_per_symbol: number;
  max_total_exposure_usd: number;
  max_realized_loss_usd: number;
  loss_threshold_percent: number;
  required_pyramids_for_timer: number;
  post_pyramids_wait_minutes: number;
  max_winners_to_combine: number;
  // Priority rules are internal but exposed for QueuePage display
  priority_rules?: PriorityRulesConfig;
}

export interface TelegramConfig {
  enabled: boolean;
  bot_token?: string;
  channel_id?: string;
  channel_name: string;
  engine_signature: string;
  send_entry_signals: boolean;
  send_exit_signals: boolean;
  update_on_pyramid: boolean;
  test_mode: boolean;
}

export interface UserSettings {
  id: string;
  username: string;
  email: string;
  exchange: string;
  webhook_secret: string;
  configured_exchanges: string[];
  risk_config: RiskEngineConfig;
  telegram_config?: TelegramConfig;
  configured_exchange_details?: Record<string, { testnet?: boolean; account_type?: string; encrypted_data?: string; }>;
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
      useNotificationStore.getState().showNotification('Settings updated successfully!', 'success');
    } catch (err: any) {
      console.error("Failed to update settings", err);
      let errorMessage = 'Failed to update settings';
      if (err.response?.data?.detail) {
        if (Array.isArray(err.response.data.detail)) {
          errorMessage = err.response.data.detail.map((e: any) => e.msg).join(', ');
        } else if (typeof err.response.data.detail === 'string') {
          errorMessage = err.response.data.detail;
        } else {
          errorMessage = JSON.stringify(err.response.data.detail);
        }
      } else if (err.message) {
        errorMessage = err.message;
      }
      set({ error: errorMessage, loading: false });
      useNotificationStore.getState().showNotification(`Failed to update settings: ${errorMessage}`, 'error');
    }
  },

  deleteKey: async (exchange: string) => {
    set({ loading: true, error: null });
    try {
      const response = await api.delete<UserSettings>(`/settings/keys/${exchange}`);
      set({ settings: response.data, loading: false });
      // Also update the user in the auth store
      useAuthStore.getState().login(useAuthStore.getState().token!, response.data);
      useNotificationStore.getState().showNotification(`Keys for ${exchange} removed successfully!`, 'success');
    } catch (err: any) {
      console.error("Failed to delete key", err);
      set({ error: err.response?.data?.detail || 'Failed to delete key', loading: false });
      useNotificationStore.getState().showNotification(`Failed to delete key: ${err.response?.data?.detail || err.message}`, 'error');
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
