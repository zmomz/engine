import { create } from 'zustand';
import axios from 'axios';

interface EngineState {
  tvl: number | null;
  pnl: number | null;
  activeGroupsCount: number | null;
  fetchEngineData: () => Promise<void>;
  // Add other state properties as needed for the dashboard widgets
}

const useEngineStore = create<EngineState>((set) => ({
  tvl: null,
  pnl: null,
  activeGroupsCount: null,

  fetchEngineData: async () => {
    try {
      // Replace with actual API endpoints
      const tvlResponse = await axios.get('/api/dashboard/tvl');
      const pnlResponse = await axios.get('/api/dashboard/pnl');
      const activeGroupsResponse = await axios.get('/api/dashboard/active-groups-count');

      set({
        tvl: tvlResponse.data.tvl,
        pnl: pnlResponse.data.pnl,
        activeGroupsCount: activeGroupsResponse.data.count,
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
