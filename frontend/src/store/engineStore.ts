import { create } from 'zustand';
import api from '../services/api';

interface EngineState {
  tvl: number | null;
  pnl: number | null;
  realized_pnl: number | null;
  unrealized_pnl: number | null;
  activeGroupsCount: number | null;
  free_usdt: number | null;
  total_trades: number | null;
  total_winning_trades: number | null;
  total_losing_trades: number | null;
  win_rate: number | null;
  fetchEngineData: () => Promise<void>;
}

const useEngineStore = create<EngineState>((set) => ({
  tvl: null,
  pnl: null,
  realized_pnl: null,
  unrealized_pnl: null,
  activeGroupsCount: null,
  free_usdt: null,
  total_trades: null,
  total_winning_trades: null,
  total_losing_trades: null,
  win_rate: null,

  fetchEngineData: async () => {
    try {
      const accountSummaryResponse = await api.get('/dashboard/account-summary');
      const pnlResponse = await api.get('/dashboard/pnl');
      const activeGroupsResponse = await api.get('/dashboard/active-groups-count');
      const statsResponse = await api.get('/dashboard/stats');

      set({
        tvl: accountSummaryResponse.data.tvl,
        free_usdt: accountSummaryResponse.data.free_usdt,
        pnl: pnlResponse.data.pnl,
        realized_pnl: pnlResponse.data.realized_pnl,
        unrealized_pnl: pnlResponse.data.unrealized_pnl,
        activeGroupsCount: activeGroupsResponse.data.count,
        total_trades: statsResponse.data.total_trades,
        total_winning_trades: statsResponse.data.total_winning_trades,
        total_losing_trades: statsResponse.data.total_losing_trades,
        win_rate: statsResponse.data.win_rate,
      });
    } catch (error) {
      console.error("Failed to fetch engine data", error);
      // Handle error, maybe set state to indicate loading failure
    }
  },
}));

// Polling logic (example: poll every 5 seconds)
const pollingInterval = 5000; // 5 seconds
let intervalId: NodeJS.Timeout | null = null;

export const startEngineDataPolling = () => {
  if (intervalId) return; // Already running
  intervalId = setInterval(() => {
    useEngineStore.getState().fetchEngineData();
  }, pollingInterval);
};

export const stopEngineDataPolling = () => {
  if (intervalId) {
    clearInterval(intervalId);
    intervalId = null;
  }
};

export default useEngineStore;
