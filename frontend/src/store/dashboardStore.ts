import { create } from 'zustand';
import api from '../services/api';

interface LiveDashboard {
  total_active_position_groups: number;
  queued_signals_count: number;
  total_pnl_usd: number;
  realized_pnl_usd: number;
  unrealized_pnl_usd: number;
  pnl_today: number;
  total_trades: number;
  wins: number;
  losses: number;
  win_rate: number;
  tvl: number;
  free_usdt: number;
  last_webhook_timestamp: string | null;
  engine_status: string;
  risk_engine_status: string;
}

interface PnLMetrics {
  realized_pnl: number;
  unrealized_pnl: number;
  total_pnl: number;
  pnl_today: number;
  pnl_week: number;
  pnl_month: number;
  pnl_all_time: number;
  pnl_by_pair: Record<string, number>;
  pnl_by_timeframe: Record<string, number>;
}

interface EquityCurvePoint {
  timestamp: string | null;
  equity: number;
}

interface WinLossStats {
  total_trades: number;
  wins: number;
  losses: number;
  win_rate: number;
  avg_win: number;
  avg_loss: number;
  rr_ratio: number;
}

interface TradeDistribution {
  returns: number[];
  best_trades: [string, number][];
  worst_trades: [string, number][];
}

interface RiskMetrics {
  max_drawdown: number;
  current_drawdown: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  profit_factor: number;
}

interface PerformanceDashboard {
  pnl_metrics: PnLMetrics;
  equity_curve: EquityCurvePoint[];
  win_loss_stats: WinLossStats;
  trade_distribution: TradeDistribution;
  risk_metrics: RiskMetrics;
}

interface DashboardData {
  live_dashboard: LiveDashboard;
  performance_dashboard: PerformanceDashboard;
  timestamp: string;
}

interface DashboardStore {
  data: DashboardData | null;
  loading: boolean;
  error: string | null;
  fetchDashboardData: (isBackground?: boolean) => Promise<void>;
}

// Track in-flight request to prevent duplicate calls
let pendingRequest: Promise<void> | null = null;

const useDashboardStore = create<DashboardStore>((set) => ({
  data: null,
  loading: false,
  error: null,

  fetchDashboardData: async (isBackground = false) => {
    // Deduplicate: if there's already a pending request, wait for it
    if (pendingRequest) {
      return pendingRequest;
    }

    if (!isBackground) set({ loading: true, error: null });

    pendingRequest = (async () => {
      try {
        const response = await api.get('/dashboard/analytics');
        set({ data: response.data, loading: false });
      } catch (error: any) {
        console.error('Failed to fetch dashboard data', error);
        if (!isBackground) {
          set({
            error: error.response?.data?.detail || 'Failed to fetch dashboard data',
            loading: false
          });
        }
      } finally {
        pendingRequest = null;
      }
    })();

    return pendingRequest;
  },
}));

// Polling logic (every 1 second for real-time feel)
const pollingInterval = 1000;
let intervalId: NodeJS.Timeout | null = null;

export const startDashboardPolling = () => {
  if (intervalId) return;
  intervalId = setInterval(() => {
    useDashboardStore.getState().fetchDashboardData(true);
  }, pollingInterval);
};

export const stopDashboardPolling = () => {
  if (intervalId) {
    clearInterval(intervalId);
    intervalId = null;
  }
};

export default useDashboardStore;
