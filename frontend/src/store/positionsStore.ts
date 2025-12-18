import { create } from 'zustand';
import api from '../services/api';
import useNotificationStore from './notificationStore';

export interface DCAOrder {
  id: string;
  price: number;
  quantity: number;
  filled_quantity: number | null;
  status: string;
  order_type: string;
}

export interface Pyramid {
  id: string;
  entry_price: number;
  status: string;
  dca_orders: DCAOrder[];
}

export interface PositionGroup {
  id: string;
  exchange: string;
  symbol: string;
  timeframe: number;
  side: string;
  status: string;
  pyramid_count: number;
  max_pyramids: number;
  replacement_count: number;
  total_dca_legs: number;
  filled_dca_legs: number;
  base_entry_price: number;
  weighted_avg_entry: number;
  total_invested_usd: number;
  total_filled_quantity: number;
  unrealized_pnl_usd: number;
  unrealized_pnl_percent: number;
  realized_pnl_usd: number;
  tp_mode: string;
  risk_timer_expires: string | null;
  risk_eligible: boolean;
  risk_blocked: boolean;
  created_at: string;
  closed_at: string | null;
  pyramids: Pyramid[];
}

interface PositionsState {
  positions: PositionGroup[];
  positionHistory: PositionGroup[];
  loading: boolean;
  error: string | null;
  fetchPositions: (isBackground?: boolean) => Promise<void>;
  fetchPositionHistory: (isBackground?: boolean) => Promise<void>;
  closePosition: (groupId: string) => Promise<void>;
  setPositions: (positions: PositionGroup[]) => void;
}

const usePositionsStore = create<PositionsState>((set, get) => ({
  positions: [],
  positionHistory: [],
  loading: false,
  error: null,

  setPositions: (positions) => set({ positions }),

  fetchPositions: async (isBackground = false) => {
    if (!isBackground) set({ loading: true, error: null });
    try {
      const response = await api.get<PositionGroup[]>('/positions/active');
      set({ positions: response.data, loading: false });
    } catch (err: any) {
      console.error("Failed to fetch positions", err);
      // Only set error if not background, or handle silently
      if (!isBackground) set({ error: err.response?.data?.detail || 'Failed to fetch positions', loading: false });
    }
  },

  fetchPositionHistory: async (isBackground = false) => {
    if (!isBackground) set({ loading: true, error: null });
    try {
      // Get user ID from the API (the backend will use current user)
      const response = await api.get<PositionGroup[]>('/positions/history');
      set({ positionHistory: response.data, loading: false });
    } catch (err: any) {
      console.error("Failed to fetch position history", err);
      if (!isBackground) set({ error: err.response?.data?.detail || 'Failed to fetch position history', loading: false });
    }
  },

  closePosition: async (groupId: string) => {
    try {
      await api.post(`/positions/${groupId}/close`);
      useNotificationStore.getState().showNotification('Position close initiated.', 'success');
      await get().fetchPositions();
    } catch (err: any) {
      console.error("Failed to close position", err);
      useNotificationStore.getState().showNotification(err.response?.data?.detail || 'Failed to force close position', 'error');
    }
  }
}));

export default usePositionsStore;