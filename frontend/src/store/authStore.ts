import { create } from 'zustand';
import api from '../services/api';

// User interface matching the backend UserSettings schema
export interface User {
  id: string;
  username: string;
  email: string;
  exchange: string;
  webhook_secret: string;
  configured_exchanges: string[];
  risk_config: {
    max_open_positions_global: number;
    max_open_positions_per_symbol: number;
    max_total_exposure_usd: number;
    max_realized_loss_usd: number;
    loss_threshold_percent: number;
    required_pyramids_for_timer: number;
    post_pyramids_wait_minutes: number;
    max_winners_to_combine: number;
    priority_rules?: {
      priority_rules_enabled: {
        same_pair_timeframe: boolean;
        deepest_loss_percent: boolean;
        highest_replacement: boolean;
        fifo_fallback: boolean;
      };
      priority_order: string[];
    };
  };
  telegram_config?: {
    // Connection
    enabled: boolean;
    bot_token?: string;
    channel_id?: string;
    channel_name: string;
    engine_signature: string;

    // Message Type Toggles
    send_entry_signals: boolean;
    send_exit_signals: boolean;
    send_status_updates: boolean;
    send_dca_fill_updates: boolean;
    send_pyramid_updates: boolean;
    send_tp_hit_updates: boolean;
    send_failure_alerts: boolean;
    send_risk_alerts: boolean;

    // Advanced Controls
    update_existing_message: boolean;
    update_on_pyramid: boolean;
    show_unrealized_pnl: boolean;
    show_invested_amount: boolean;
    show_duration: boolean;

    // Threshold Alerts
    alert_loss_threshold_percent?: number | null;
    alert_profit_threshold_percent?: number | null;

    // Quiet Hours
    quiet_hours_enabled: boolean;
    quiet_hours_start?: string | null;
    quiet_hours_end?: string | null;
    quiet_hours_urgent_only: boolean;

    // Test mode
    test_mode: boolean;
  };
  configured_exchange_details?: Record<string, {
    testnet?: boolean;
    account_type?: string;
    encrypted_data?: string;
  }>;
}

export interface AuthState {
  token: string | null;
  isAuthenticated: boolean;
  user: User | null;
  login: (token: string, user: User) => void;
  logout: () => void;
  initializeAuth: () => void;
  register: (username: string, email: string, password: string) => Promise<void>;
}

const getUserFromStorage = () => {
  const item = localStorage.getItem('user');
  if (!item || item === 'undefined') return null;
  try {
    return JSON.parse(item);
  } catch {
    return null;
  }
};

const useAuthStore = create<AuthState>((set, get) => ({
  token: localStorage.getItem('token'),
  isAuthenticated: !!localStorage.getItem('token'),
  user: getUserFromStorage(),

  login: (token, user) => {
    localStorage.setItem('token', token);
    localStorage.setItem('user', JSON.stringify(user || null));
    set({ token, isAuthenticated: true, user });
  },

  logout: () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    set({ token: null, isAuthenticated: false, user: null });
  },

  initializeAuth: () => {
    const token = localStorage.getItem('token');
    const user = getUserFromStorage();
    set({ token, isAuthenticated: !!token, user });
  },

  register: async (username, email, password) => {
    try {
      // 1. Register
      const registerResponse = await api.post('/users/register', {
        username,
        email,
        password,
      });
      const user = registerResponse.data;

      // 2. Login to get token
      const params = new URLSearchParams();
      params.append('username', username);
      params.append('password', password);

      const loginResponse = await api.post('/users/login', params, {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      });

      const token = loginResponse.data.access_token;

      // 3. Update store
      get().login(token, user);

    } catch (error) {
      console.error("Registration failed:", error);
      throw error; // Re-throw for component to handle
    }
  },
}));

export default useAuthStore;