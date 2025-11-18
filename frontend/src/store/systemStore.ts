import { create } from 'zustand';

type EngineStatus = 'Running' | 'Stopped' | 'Error';
type Theme = 'light' | 'dark';

interface SystemStore {
  engineStatus: EngineStatus;
  riskEngineStatus: string;
  lastWebhookTimestamp: string | null;
  alerts: any[];
  theme: Theme;
  setEngineStatus: (status: EngineStatus) => void;
  addAlert: (alert: any) => void;
  clearAlerts: () => void;
  toggleTheme: () => void;
}

export const useSystemStore = create<SystemStore>((set) => ({
  engineStatus: 'Stopped',
  riskEngineStatus: 'Idle',
  lastWebhookTimestamp: null,
  alerts: [],
  theme: 'light',
  setEngineStatus: (status) => set({ engineStatus: status }),
  addAlert: (alert) => set((state) => ({ alerts: [...state.alerts, alert] })),
  clearAlerts: () => set({ alerts: [] }),
  toggleTheme: () =>
    set((state) => ({ theme: state.theme === 'light' ? 'dark' : 'light' })),
}));
