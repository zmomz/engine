import { create } from 'zustand';
import api from '../services/api';
import useAuthStore, { User } from './authStore';
import useNotificationStore from './notificationStore';

// Re-export User as UserSettings for backward compatibility
export type UserSettings = User;

// Additional type exports for components that need specific config types
export type RiskEngineConfig = User['risk_config'];
export type TelegramConfig = NonNullable<User['telegram_config']>;
export type PriorityRulesConfig = NonNullable<RiskEngineConfig['priority_rules']>;

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
      const response = await api.get<UserSettings>('/settings');
      set({ settings: response.data, loading: false });
      // Also update the user in the auth store to keep them in sync
      const token = useAuthStore.getState().token;
      if (token) {
        useAuthStore.getState().login(token, response.data);
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
