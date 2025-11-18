import { create } from 'zustand';

interface PnlMetrics {
  unrealized_pnl: number;
  realized_pnl: number;
  total_pnl: number;
}

interface PoolUsage {
  active: number;
  max: number;
}

interface DataStore {
  positionGroups: any[];
  queuedSignals: any[];
  poolUsage: PoolUsage;
  pnlMetrics: PnlMetrics;
  updatePositionGroups: (groups: any[]) => void;
  updateQueuedSignals: (signals: any[]) => void;
  setInitialData: (data: {
    positionGroups: any[];
    queuedSignals: any[];
    poolUsage: PoolUsage;
    pnlMetrics: PnlMetrics;
  }) => void;
}

export const useDataStore = create<DataStore>((set) => ({
  positionGroups: [],
  queuedSignals: [],
  poolUsage: { active: 0, max: 0 },
  pnlMetrics: {
    unrealized_pnl: 0,
    realized_pnl: 0,
    total_pnl: 0,
  },
  updatePositionGroups: (groups) => set({ positionGroups: groups }),
  updateQueuedSignals: (signals) => set({ queuedSignals: signals }),
  setInitialData: (data) => set(data),
}));
