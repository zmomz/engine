import { create } from 'zustand';
import axios from 'axios';
import useAuthStore from './authStore';

interface HistoricalPosition {
  id: string;
  symbol: string;
  side: string;
  close_time: string;
  realized_pnl: number;
  // Add other relevant fields if needed
}

interface EquityCurveState {
  historicalPositions: HistoricalPosition[];
  loading: boolean;
  error: string | null;
  fetchHistoricalPositions: () => Promise<void>;
}

const useEquityCurveStore = create<EquityCurveState>((set) => ({
  historicalPositions: [],
  loading: false,
  error: null,

  fetchHistoricalPositions: async () => {
    set({ loading: true, error: null });
    const userId = useAuthStore.getState().user?.id; // Get user ID from auth store

    if (!userId) {
      set({ error: 'User not authenticated', loading: false });
      return;
    }

    try {
      const response = await axios.get<HistoricalPosition[]>(`/api/v1/positions/${userId}/history`);
      set({ historicalPositions: response.data, loading: false });
    } catch (err: any) {
      console.error("Failed to fetch historical positions", err);
      set({ error: err.response?.data?.detail || 'Failed to fetch historical positions', loading: false });
    }
  },
}));

export default useEquityCurveStore;
