import { create } from 'zustand';
import api from '../services/api';
import useNotificationStore from './notificationStore';

export interface DCAOrder {
  id: string;
  price: number;
  amount: number;
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
  symbol: string;
  side: string;
  status: string;
  unrealized_pnl_usd: number;
  unrealized_pnl_percent: number;
  total_invested_usd: number;
  pyramids: Pyramid[];
}

interface PositionsState {
  positions: PositionGroup[];
  loading: boolean;
  error: string | null;
  fetchPositions: () => Promise<void>;
  closePosition: (groupId: string) => Promise<void>;
  setPositions: (positions: PositionGroup[]) => void;
}

const usePositionsStore = create<PositionsState>((set, get) => ({
  positions: [],
  loading: false,
  error: null,

  setPositions: (positions) => set({ positions }),

  fetchPositions: async () => {
    set({ loading: true, error: null });
    try {
      const response = await api.get<PositionGroup[]>('/positions/active');
      set({ positions: response.data, loading: false });
    } catch (err: any) {
      console.error("Failed to fetch positions", err);
      set({ error: err.response?.data?.detail || 'Failed to fetch positions', loading: false });
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