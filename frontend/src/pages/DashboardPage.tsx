import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Grid,
  Chip,
  LinearProgress,
  Button,
  Alert,
  Tooltip,
  Divider
} from '@mui/material';
import SettingsIcon from '@mui/icons-material/Settings';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import StopIcon from '@mui/icons-material/Stop';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import SyncIcon from '@mui/icons-material/Sync';
import PauseIcon from '@mui/icons-material/Pause';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import AccountBalanceWalletIcon from '@mui/icons-material/AccountBalanceWallet';
import useDashboardStore, { startDashboardPolling, stopDashboardPolling } from '../store/dashboardStore';
import useRiskStore from '../store/riskStore';
import { LiveDashboardSkeleton } from '../components/DashboardSkeleton';
import { StatusIndicatorDot } from '../components/AnimatedStatusChip';
import { DataFreshnessIndicator } from '../components/DataFreshnessIndicator';
import { AnimatedCurrency } from '../components/AnimatedValue';
import { useKeyboardShortcuts } from '../hooks/useKeyboardShortcuts';
import { useVisibilityRefresh } from '../hooks/useVisibilityRefresh';
import { safeToFixed, safeNumber } from '../utils/formatters';

const DashboardPage: React.FC = () => {
  const navigate = useNavigate();
  const { data, loading, error, fetchDashboardData } = useDashboardStore();
  const {
    status: riskStatus,
    fetchStatus: fetchRiskStatus,
    forceStop,
    forceStart,
    syncExchange,
    error: riskError
  } = useRiskStore();
  const [syncing, setSyncing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  // Keyboard shortcuts
  useKeyboardShortcuts({
    onRefresh: () => {
      fetchDashboardData();
      fetchRiskStatus();
      setLastUpdated(new Date());
    },
  });

  // Refresh data when tab becomes visible again
  useVisibilityRefresh(() => {
    fetchDashboardData();
    fetchRiskStatus();
    setLastUpdated(new Date());
  });

  useEffect(() => {
    const fetchData = async () => {
      await fetchDashboardData();
      await fetchRiskStatus();
      setLastUpdated(new Date());
    };

    fetchData();
    startDashboardPolling();
    const riskInterval = setInterval(async () => {
      await fetchRiskStatus(true);
      setLastUpdated(new Date());
    }, 1000);
    return () => {
      stopDashboardPolling();
      clearInterval(riskInterval);
    };
  }, [fetchDashboardData, fetchRiskStatus]);

  const handleSyncExchange = async () => {
    setSyncing(true);
    await syncExchange();
    setSyncing(false);
  };

  const getQueueStatusInfo = () => {
    if (riskStatus?.engine_force_stopped) {
      return { label: 'Stopped', color: 'error' as const, icon: <StopIcon fontSize="small" /> };
    }
    // Check if loss limit exceeded (frontend calculation)
    const limit = safeNumber(riskStatus?.max_realized_loss_usd ?? 500);
    const loss = Math.abs(Math.min(0, safeNumber(riskStatus?.daily_realized_pnl ?? 0)));
    if (loss >= limit || riskStatus?.engine_paused_by_loss_limit) {
      return { label: 'Paused', color: 'warning' as const, icon: <PauseIcon fontSize="small" /> };
    }
    return { label: 'Running', color: 'success' as const, icon: <CheckCircleIcon fontSize="small" /> };
  };

  const queueStatusInfo = getQueueStatusInfo();

  const formatCurrency = (value: number | string | undefined | null) => {
    const num = safeNumber(value);
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    }).format(num);
  };

  const formatPercent = (value: number) => {
    return `${safeToFixed(value)}%`;
  };

  if (loading && !data) {
    return (
      <Box sx={{ flexGrow: 1, p: 3 }}>
        <Typography variant="h4" gutterBottom>
          Dashboard
        </Typography>
        <LiveDashboardSkeleton />
      </Box>
    );
  }

  if (error && !data) {
    return (
      <Box sx={{ p: 3 }}>
        <Typography color="error">Error: {error}</Typography>
      </Box>
    );
  }

  if (!data) {
    return (
      <Box sx={{ p: 3 }}>
        <Typography>No dashboard data available</Typography>
      </Box>
    );
  }

  const live = data.live_dashboard;
  const capitalDeployed = safeNumber(live.tvl) > 0
    ? ((safeNumber(live.tvl) - safeNumber(live.free_usdt)) / safeNumber(live.tvl)) * 100
    : 0;

  // Calculate loss limit usage (cumulative, not daily)
  const maxLossLimit = safeNumber(riskStatus?.max_realized_loss_usd ?? 500);
  const currentLoss = Math.min(0, safeNumber(riskStatus?.daily_realized_pnl ?? 0));
  const lossLimitUsage = maxLossLimit > 0 ? (Math.abs(currentLoss) / maxLossLimit) * 100 : 0;

  return (
    <Box sx={{ flexGrow: 1, p: { xs: 2, sm: 3 } }}>
      {/* Header */}
      <Box sx={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: { xs: 'flex-start', sm: 'center' },
        flexDirection: { xs: 'column', sm: 'row' },
        gap: { xs: 1, sm: 0 },
        mb: 3
      }}>
        <Typography variant="h4" sx={{ fontSize: { xs: '1.75rem', sm: '2.125rem' } }}>
          Dashboard
        </Typography>
        <DataFreshnessIndicator lastUpdated={lastUpdated} />
      </Box>

      {/* Error Alerts */}
      {riskError && (
        <Alert severity="error" sx={{ mb: 2 }}>{riskError}</Alert>
      )}

      {/* Status Bar - Compact system status */}
      <Box sx={{
        display: 'flex',
        alignItems: 'center',
        gap: { xs: 2, sm: 3 },
        p: { xs: 1.5, sm: 2 },
        bgcolor: 'background.paper',
        borderRadius: 2,
        mb: 3,
        flexWrap: 'wrap',
        boxShadow: 1
      }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <StatusIndicatorDot
            color={live.engine_status === 'running' ? 'success' : 'error'}
            pulsing={live.engine_status === 'running'}
            size={10}
          />
          <Typography variant="body2" color="text.secondary">
            Engine: <strong>{live.engine_status}</strong>
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <StatusIndicatorDot
            color={live.risk_engine_status === 'active' ? 'success' : 'warning'}
            pulsing={live.risk_engine_status === 'active'}
            size={10}
          />
          <Typography variant="body2" color="text.secondary">
            Risk Engine: <strong>{live.risk_engine_status}</strong>
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Chip
            icon={queueStatusInfo.icon}
            label={`Queue: ${queueStatusInfo.label}`}
            color={queueStatusInfo.color}
            size="small"
            variant="outlined"
          />
        </Box>
        <Typography variant="body2" color="text.secondary" sx={{ ml: 'auto' }}>
          Last webhook: {live.last_webhook_timestamp
            ? new Date(live.last_webhook_timestamp).toLocaleString()
            : 'No signals yet'}
        </Typography>
      </Box>

      <Grid container spacing={{ xs: 2, sm: 3 }}>
        {/* Account Overview Section */}
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Total PnL
              </Typography>
              <AnimatedCurrency
                value={safeNumber(live.total_pnl_usd)}
                variant="h4"
                showTrend={true}
              />
              <Box sx={{ mt: 1, display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                <Tooltip title="Realized PnL from closed trades">
                  <Typography variant="caption" color="text.secondary">
                    Realized: {formatCurrency(live.realized_pnl_usd)}
                  </Typography>
                </Tooltip>
                <Tooltip title="Unrealized PnL from open positions">
                  <Typography variant="caption" color="text.secondary">
                    Open: {formatCurrency(live.unrealized_pnl_usd)}
                  </Typography>
                </Tooltip>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Today's PnL
              </Typography>
              <AnimatedCurrency
                value={safeNumber(live.pnl_today)}
                variant="h4"
                showTrend={true}
              />
            </CardContent>
          </Card>
        </Grid>

        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Win Rate
              </Typography>
              <Typography variant="h4" sx={{
                color: safeNumber(live.win_rate) >= 50 ? 'success.main' : 'error.main'
              }}>
                {formatPercent(safeNumber(live.win_rate))}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {live.wins ?? 0}W / {live.losses ?? 0}L ({live.total_trades ?? 0} trades)
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Positions
              </Typography>
              <Typography variant="h4">
                {live.total_active_position_groups}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Active positions • {live.queued_signals_count} queued
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        {/* Capital Section */}
        <Grid size={{ xs: 12, md: 6 }}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom sx={{ fontSize: { xs: '1rem', sm: '1.25rem' } }}>
                Capital
              </Typography>
              <Box sx={{ mb: 2 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                  <Typography variant="body2" color="text.secondary">
                    TVL
                  </Typography>
                  <Typography variant="body2" fontWeight={600}>
                    {formatCurrency(live.tvl)}
                  </Typography>
                </Box>
                <LinearProgress
                  variant="determinate"
                  value={capitalDeployed}
                  sx={{
                    height: 8,
                    borderRadius: 1,
                    bgcolor: 'success.light',
                    '& .MuiLinearProgress-bar': {
                      bgcolor: 'primary.main'
                    }
                  }}
                />
                <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 0.5 }}>
                  <Typography variant="caption" color="text.secondary">
                    {formatPercent(capitalDeployed)} deployed
                  </Typography>
                  <Typography variant="caption" color="success.main">
                    {formatCurrency(live.free_usdt)} free
                  </Typography>
                </Box>
              </Box>
              <Divider sx={{ my: 2 }} />
              <Box sx={{ display: 'flex', justifyContent: 'space-around', textAlign: 'center' }}>
                <Box>
                  <Typography variant="h5" color="primary.main">
                    {formatCurrency(safeNumber(live.tvl) - safeNumber(live.free_usdt))}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    Deployed
                  </Typography>
                </Box>
                <Divider orientation="vertical" flexItem />
                <Box>
                  <Typography variant="h5" color="success.main">
                    {formatCurrency(live.free_usdt)}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    Available
                  </Typography>
                </Box>
              </Box>

              {/* Per-Exchange Balances */}
              {live.exchange_balances && Object.keys(live.exchange_balances).length > 0 && (
                <>
                  <Divider sx={{ my: 2 }} />
                  <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 1.5, display: 'flex', alignItems: 'center', gap: 0.5 }}>
                    <AccountBalanceWalletIcon fontSize="small" />
                    Exchange Balances
                  </Typography>
                  <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
                    {Object.entries(live.exchange_balances).map(([exchangeName, balance]) => (
                      <Box
                        key={exchangeName}
                        sx={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                          p: 1.5,
                          bgcolor: 'background.default',
                          borderRadius: 1,
                          borderLeft: 3,
                          borderColor: 'primary.main'
                        }}
                      >
                        <Box>
                          <Typography variant="body2" fontWeight={600} sx={{ textTransform: 'capitalize' }}>
                            {exchangeName}
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            Free: {formatCurrency(balance.free_usdt)}
                          </Typography>
                        </Box>
                        <Typography variant="body1" fontWeight={600} color="primary.main">
                          {formatCurrency(balance.tvl)}
                        </Typography>
                      </Box>
                    ))}
                  </Box>
                </>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Controls & Safety Section */}
        <Grid size={{ xs: 12, md: 6 }}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom sx={{ fontSize: { xs: '1rem', sm: '1.25rem' } }}>
                Controls & Safety
              </Typography>

              {/* Control Buttons */}
              <Box sx={{ display: 'flex', gap: 1, mb: 3, flexWrap: 'wrap' }}>
                {riskStatus?.engine_force_stopped || lossLimitUsage >= 100 ? (
                  <Button
                    variant="contained"
                    color="success"
                    startIcon={<PlayArrowIcon />}
                    onClick={forceStart}
                    size="small"
                  >
                    Start Queue
                  </Button>
                ) : (
                  <Button
                    variant="contained"
                    color="error"
                    startIcon={<StopIcon />}
                    onClick={forceStop}
                    size="small"
                  >
                    Stop Queue
                  </Button>
                )}
                <Button
                  variant="outlined"
                  startIcon={<SyncIcon />}
                  onClick={handleSyncExchange}
                  disabled={syncing}
                  size="small"
                >
                  {syncing ? 'Syncing...' : 'Sync Exchange'}
                </Button>
              </Box>

              {/* Warning messages */}
              {lossLimitUsage >= 100 && (
                <Alert
                  severity="warning"
                  sx={{ mb: 2 }}
                  icon={<WarningAmberIcon />}
                  action={
                    <Button
                      color="inherit"
                      size="small"
                      startIcon={<SettingsIcon />}
                      onClick={() => navigate('/settings')}
                    >
                      Adjust Limit
                    </Button>
                  }
                >
                  Queue paused: Loss limit reached. Increase the limit in Settings to resume.
                </Alert>
              )}
              {riskStatus?.engine_force_stopped && (
                <Alert severity="error" sx={{ mb: 2 }}>
                  Queue stopped manually. Click "Start Queue" to resume.
                </Alert>
              )}

              {/* Safety Limits */}
              <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 1 }}>
                Safety Limits
              </Typography>
              <Box sx={{
                bgcolor: 'background.default',
                borderRadius: 1,
                p: 2
              }}>
                {/* Loss Circuit Breaker */}
                <Box sx={{ mb: 2 }}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.5 }}>
                    <Tooltip title="Queue stops accepting new trades when cumulative realized losses reach this limit">
                      <Typography variant="body2" color="text.secondary" sx={{ cursor: 'help' }}>
                        Loss Circuit Breaker
                      </Typography>
                    </Tooltip>
                    <Typography
                      variant="body2"
                      fontWeight={600}
                      color={lossLimitUsage > 80 ? 'error.main' : lossLimitUsage > 50 ? 'warning.main' : 'text.primary'}
                    >
                      {formatCurrency(Math.abs(currentLoss))} / {formatCurrency(maxLossLimit)}
                    </Typography>
                  </Box>
                  <LinearProgress
                    variant="determinate"
                    value={Math.min(lossLimitUsage, 100)}
                    color={lossLimitUsage > 80 ? 'error' : lossLimitUsage > 50 ? 'warning' : 'primary'}
                    sx={{ height: 6, borderRadius: 1 }}
                  />
                </Box>

                {/* Max Positions */}
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Typography variant="body2" color="text.secondary">
                    Max Positions
                  </Typography>
                  <Typography variant="body2">
                    {live.total_active_position_groups} / {riskStatus?.config?.max_open_positions_global ?? 10}
                  </Typography>
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
};

export default DashboardPage;
