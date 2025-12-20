import React, { useEffect, useMemo } from 'react';
import {
  Box,
  Typography,
  Button,
  Card,
  CardContent,
  Grid,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  LinearProgress,
  Divider,
  IconButton,
  Alert
} from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import CancelIcon from '@mui/icons-material/Cancel';
import TimerIcon from '@mui/icons-material/Timer';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import RefreshIcon from '@mui/icons-material/Refresh';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import StopIcon from '@mui/icons-material/Stop';
import ViewListIcon from '@mui/icons-material/ViewList';
import TimelineIcon from '@mui/icons-material/Timeline';
import useRiskStore from '../store/riskStore';
import useConfirmStore from '../store/confirmStore';
import { RiskPageSkeleton } from '../components/RiskSkeleton';
import { safeToFixed, safeNumber } from '../utils/formatters';
import { MetricCard } from '../components/MetricCard';
import { DataFreshnessIndicator } from '../components/DataFreshnessIndicator';
import { Timeline, TimelineItem } from '../components/Timeline';
import { useKeyboardShortcuts } from '../hooks/useKeyboardShortcuts';
import { OffsetPreviewDialog, OffsetPreviewData } from '../components/OffsetPreviewDialog';
import { StatusIndicatorDot } from '../components/AnimatedStatusChip';

const RiskPage: React.FC = () => {
  const { status, loading, error, fetchStatus, runEvaluation, blockGroup, unblockGroup, skipGroup, forceStart, forceStop } = useRiskStore();
  const [lastUpdated, setLastUpdated] = React.useState<Date | null>(null);
  const [actionsView, setActionsView] = React.useState<'table' | 'timeline'>('timeline');
  const [offsetPreviewOpen, setOffsetPreviewOpen] = React.useState(false);
  const [offsetPreviewData, setOffsetPreviewData] = React.useState<OffsetPreviewData | null>(null);
  const [executingOffset, setExecutingOffset] = React.useState(false);

  // Keyboard shortcuts
  useKeyboardShortcuts({
    onRefresh: () => {
      fetchStatus();
      setLastUpdated(new Date());
    },
    onForceStart: () => forceStart(),
    onForceStop: () => forceStop(),
    onRunRiskEvaluation: () => runEvaluation(),
  });

  useEffect(() => {
    const fetchData = async () => {
      await fetchStatus();
      setLastUpdated(new Date());
    };
    fetchData();
    const interval = setInterval(() => fetchData(), 5000);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  const handleRunEvaluation = async () => {
    const confirmed = await useConfirmStore.getState().requestConfirm({
      title: 'Run Evaluation',
      message: 'Are you sure you want to run a manual risk evaluation?',
      confirmText: 'Run',
    });
    if (confirmed) {
      runEvaluation();
    }
  };

  const handleBlock = async (groupId: string) => {
    const confirmed = await useConfirmStore.getState().requestConfirm({
      title: 'Block Position',
      message: 'Are you sure you want to block this position from risk evaluation?',
      confirmText: 'Block',
    });
    if (confirmed) {
      blockGroup(groupId);
    }
  };

  const handleUnblock = async (groupId: string) => {
    const confirmed = await useConfirmStore.getState().requestConfirm({
      title: 'Unblock Position',
      message: 'Are you sure you want to unblock this position?',
      confirmText: 'Unblock',
    });
    if (confirmed) {
      unblockGroup(groupId);
    }
  };

  const handleSkip = async (groupId: string) => {
    const confirmed = await useConfirmStore.getState().requestConfirm({
      title: 'Skip Next Evaluation',
      message: 'Are you sure you want to skip the next risk evaluation for this position?',
      confirmText: 'Skip',
    });
    if (confirmed) {
      skipGroup(groupId);
    }
  };

  const handleExecuteOffsetClick = () => {
    if (!status || !status.identified_loser || !status.projected_plan || status.projected_plan.length === 0) {
      return;
    }

    const previewData: OffsetPreviewData = {
      loser: status.identified_loser,
      winners: status.projected_plan,
      required_offset_usd: status.required_offset_usd,
      total_available_profit: status.total_available_profit
    };

    setOffsetPreviewData(previewData);
    setOffsetPreviewOpen(true);
  };

  const handleExecuteOffset = async () => {
    setExecutingOffset(true);
    try {
      await runEvaluation();
      setOffsetPreviewOpen(false);
      setOffsetPreviewData(null);
      await fetchStatus();
      setLastUpdated(new Date());
    } catch (error) {
      console.error('Failed to execute offset:', error);
    } finally {
      setExecutingOffset(false);
    }
  };

  const formatTimestamp = (timestamp: string | null) => {
    if (!timestamp) return 'N/A';
    return new Date(timestamp).toLocaleString();
  };

  // Calculate metrics
  const metrics = useMemo(() => {
    if (!status) return null;

    const atRiskCount = status.at_risk_positions?.length || 0;
    const recentOffsets = status.recent_actions?.length || 0;
    const totalOffsetAmount = status.recent_actions?.reduce((sum, a) => sum + Math.abs(safeNumber(a.loser_pnl_usd)), 0) || 0;
    const winnersUsed = status.recent_actions?.reduce((sum, a) => sum + (a.winners_count || 0), 0) || 0;
    const maxLoss = safeNumber(status.max_realized_loss_usd) || 500;
    const currentLoss = Math.abs(Math.min(0, safeNumber(status.daily_realized_pnl)));
    const lossPercent = maxLoss > 0 ? (currentLoss / maxLoss) * 100 : 0;

    return {
      atRiskCount,
      recentOffsets,
      totalOffsetAmount,
      winnersUsed,
      maxLoss,
      currentLoss,
      lossPercent
    };
  }, [status]);

  // Engine status info
  const getEngineStatus = () => {
    if (!status) return { label: 'Unknown', color: 'info' as const, running: false };
    if (status.engine_force_stopped) return { label: 'Stopped', color: 'error' as const, running: false };
    if (status.engine_paused_by_loss_limit) return { label: 'Paused', color: 'warning' as const, running: false };
    return { label: 'Active', color: 'success' as const, running: true };
  };

  const engineStatus = getEngineStatus();

  // Show skeleton on initial load
  if (loading && !status) {
    return <RiskPageSkeleton />;
  }

  return (
    <Box sx={{ flexGrow: 1, p: { xs: 2, sm: 3 } }}>
      {/* Header */}
      <Box sx={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: { xs: 'flex-start', sm: 'center' },
        flexDirection: { xs: 'column', sm: 'row' },
        gap: { xs: 2, sm: 0 },
        mb: 3,
      }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Typography variant="h4" sx={{ fontSize: { xs: '1.5rem', sm: '2.125rem' } }}>
            Risk
          </Typography>
          <Chip
            icon={<StatusIndicatorDot color={engineStatus.color} pulsing={engineStatus.running} size={8} />}
            label={engineStatus.label}
            color={engineStatus.color}
            size="small"
            variant="outlined"
          />
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
          <Button
            variant="contained"
            color="primary"
            size="small"
            onClick={handleRunEvaluation}
            disabled={loading}
            startIcon={<PlayArrowIcon />}
          >
            Run Evaluation
          </Button>
          <DataFreshnessIndicator lastUpdated={lastUpdated} />
          <IconButton
            onClick={() => { fetchStatus(); setLastUpdated(new Date()); }}
            color="primary"
            size="small"
          >
            <RefreshIcon />
          </IconButton>
        </Box>
      </Box>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      {/* Status Bar */}
      {status && metrics && (
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
            <Typography variant="body2" color="text.secondary">
              Engine:
            </Typography>
            <Chip
              label={engineStatus.label}
              color={engineStatus.color}
              size="small"
            />
            {status.engine_force_stopped && (
              <Button size="small" variant="outlined" color="success" onClick={forceStart} startIcon={<PlayArrowIcon />}>
                Start
              </Button>
            )}
            {!status.engine_force_stopped && !status.engine_paused_by_loss_limit && (
              <Button size="small" variant="outlined" color="error" onClick={forceStop} startIcon={<StopIcon />}>
                Stop
              </Button>
            )}
          </Box>
          <Divider orientation="vertical" flexItem />
          <Box sx={{ flex: 1, minWidth: 200 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
              <Typography variant="body2" color="text.secondary">
                Loss Circuit Breaker
              </Typography>
              <Typography
                variant="body2"
                fontWeight={600}
                color={metrics.lossPercent > 80 ? 'error.main' : metrics.lossPercent > 50 ? 'warning.main' : 'text.primary'}
              >
                ${safeToFixed(metrics.currentLoss)} / ${safeToFixed(metrics.maxLoss)}
              </Typography>
            </Box>
            <LinearProgress
              variant="determinate"
              value={Math.min(metrics.lossPercent, 100)}
              color={metrics.lossPercent > 80 ? 'error' : metrics.lossPercent > 50 ? 'warning' : 'primary'}
              sx={{ height: 6, borderRadius: 1 }}
            />
          </Box>
        </Box>
      )}

      {/* Warning if paused */}
      {status?.engine_paused_by_loss_limit && (
        <Alert severity="warning" sx={{ mb: 3 }} icon={<WarningAmberIcon />}>
          Engine paused: Loss limit reached. No new trades will be processed until reset.
        </Alert>
      )}

      {status && metrics && (
        <>
          {/* Summary Metrics */}
          <Grid container spacing={{ xs: 2, sm: 3 }} sx={{ mb: 3 }}>
            <Grid size={{ xs: 6, sm: 6, md: 3 }}>
              <MetricCard
                label="At-Risk Positions"
                value={metrics.atRiskCount.toString()}
                subtitle={metrics.atRiskCount > 0 ? 'Monitoring' : 'None'}
                icon={<WarningAmberIcon />}
                colorScheme={metrics.atRiskCount > 0 ? 'bearish' : 'neutral'}
                variant="small"
              />
            </Grid>
            <Grid size={{ xs: 6, sm: 6, md: 3 }}>
              <MetricCard
                label="Offsets Executed"
                value={metrics.recentOffsets.toString()}
                subtitle="Recent"
                icon={<CheckCircleIcon />}
                colorScheme="neutral"
                variant="small"
              />
            </Grid>
            <Grid size={{ xs: 6, sm: 6, md: 3 }}>
              <MetricCard
                label="Total Offset"
                value={`$${safeToFixed(metrics.totalOffsetAmount)}`}
                subtitle="Loss recovered"
                icon={<CheckCircleIcon />}
                colorScheme={metrics.totalOffsetAmount > 0 ? 'bullish' : 'neutral'}
                variant="small"
              />
            </Grid>
            <Grid size={{ xs: 6, sm: 6, md: 3 }}>
              <MetricCard
                label="Winners Used"
                value={metrics.winnersUsed.toString()}
                subtitle="For offsets"
                icon={<CheckCircleIcon />}
                colorScheme="neutral"
                variant="small"
              />
            </Grid>
          </Grid>

          <Grid container spacing={{ xs: 2, sm: 3 }}>
            {/* Current Evaluation - Prominent */}
            <Grid size={{ xs: 12, lg: 6 }}>
              <Card sx={{
                borderLeft: 4,
                borderColor: status.identified_loser ? 'error.main' : 'divider',
                height: '100%'
              }}>
                <CardContent>
                  <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    Current Evaluation
                    {status.identified_loser && (
                      <Chip label="Loser Identified" color="error" size="small" />
                    )}
                  </Typography>

                  {status.identified_loser ? (
                    <Box>
                      {/* Loser Summary */}
                      <Box sx={{
                        p: 2,
                        bgcolor: 'error.dark',
                        borderRadius: 1,
                        mb: 2,
                        color: 'error.contrastText'
                      }}>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 1 }}>
                          <Typography variant="h6" fontWeight={700}>
                            {status.identified_loser.symbol}
                          </Typography>
                          <Box sx={{ textAlign: 'right' }}>
                            <Typography variant="h6" fontWeight={700}>
                              ${safeToFixed(status.identified_loser.unrealized_pnl_usd)}
                            </Typography>
                            <Typography variant="caption">
                              {safeToFixed(status.identified_loser.unrealized_pnl_percent)}%
                            </Typography>
                          </Box>
                        </Box>
                        <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                          <Typography variant="body2">
                            Pyramids: {status.identified_loser.pyramid_count}/{status.identified_loser.max_pyramids}
                          </Typography>
                          <Typography variant="body2">
                            Age: {status.identified_loser.age_minutes}m
                          </Typography>
                          {status.identified_loser.timer_status === 'active' && (
                            <Chip
                              icon={<TimerIcon />}
                              label={`${status.identified_loser.timer_remaining_minutes}m`}
                              size="small"
                              sx={{ bgcolor: 'warning.main', color: 'warning.contrastText' }}
                            />
                          )}
                        </Box>
                      </Box>

                      {/* Eligibility */}
                      <Box sx={{ mb: 2 }}>
                        <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                          Eligibility
                        </Typography>
                        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                          <Chip
                            icon={status.identified_loser.pyramids_reached ? <CheckCircleIcon /> : <CancelIcon />}
                            label="Pyramids"
                            color={status.identified_loser.pyramids_reached ? 'success' : 'default'}
                            size="small"
                            variant="outlined"
                          />
                          <Chip
                            icon={status.identified_loser.age_filter_passed ? <CheckCircleIcon /> : <CancelIcon />}
                            label="Age Filter"
                            color={status.identified_loser.age_filter_passed ? 'success' : 'default'}
                            size="small"
                            variant="outlined"
                          />
                          <Chip
                            icon={!status.identified_loser.risk_blocked ? <CheckCircleIcon /> : <CancelIcon />}
                            label={status.identified_loser.risk_blocked ? 'Blocked' : 'Not Blocked'}
                            color={!status.identified_loser.risk_blocked ? 'success' : 'error'}
                            size="small"
                            variant="outlined"
                          />
                        </Box>
                      </Box>

                      {/* Offset Plan */}
                      {status.projected_plan && status.projected_plan.length > 0 && (
                        <Box sx={{ mb: 2 }}>
                          <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                            Offset Plan (Need: ${safeToFixed(status.required_offset_usd)})
                          </Typography>
                          <Box sx={{ bgcolor: 'background.default', borderRadius: 1, p: 1.5 }}>
                            {status.projected_plan.map((plan, idx) => (
                              <Box key={idx} sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                                <Typography variant="body2">
                                  {plan.symbol} {plan.partial && '(partial)'}
                                </Typography>
                                <Typography variant="body2" fontWeight={600} color="success.main">
                                  ${safeToFixed(plan.amount_to_close)}
                                </Typography>
                              </Box>
                            ))}
                            <Divider sx={{ my: 1 }} />
                            <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                              <Typography variant="body2" fontWeight={600}>Available</Typography>
                              <Typography variant="body2" fontWeight={600} color="success.main">
                                ${safeToFixed(status.total_available_profit)}
                              </Typography>
                            </Box>
                          </Box>
                        </Box>
                      )}

                      {/* Actions */}
                      <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                        {status.projected_plan && status.projected_plan.length > 0 &&
                          status.identified_loser.pyramids_reached &&
                          status.identified_loser.age_filter_passed && (
                            <Button
                              variant="contained"
                              color="error"
                              size="small"
                              onClick={handleExecuteOffsetClick}
                              startIcon={<PlayArrowIcon />}
                            >
                              Execute Offset
                            </Button>
                          )}
                        {!status.identified_loser.risk_blocked ? (
                          <Button
                            variant="outlined"
                            color="warning"
                            size="small"
                            onClick={() => handleBlock(status.identified_loser!.id)}
                          >
                            Block
                          </Button>
                        ) : (
                          <Button
                            variant="outlined"
                            color="success"
                            size="small"
                            onClick={() => handleUnblock(status.identified_loser!.id)}
                          >
                            Unblock
                          </Button>
                        )}
                        {!status.identified_loser.risk_skip_once && (
                          <Button
                            variant="outlined"
                            color="info"
                            size="small"
                            onClick={() => handleSkip(status.identified_loser!.id)}
                          >
                            Skip Next
                          </Button>
                        )}
                      </Box>
                    </Box>
                  ) : (
                    <Box sx={{ textAlign: 'center', py: 4 }}>
                      <CheckCircleIcon sx={{ fontSize: 48, color: 'success.main', mb: 1 }} />
                      <Typography variant="body1" color="text.secondary">
                        No position currently selected for offset
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        Positions will appear when loss threshold is exceeded
                      </Typography>
                    </Box>
                  )}
                </CardContent>
              </Card>
            </Grid>

            {/* Configuration */}
            <Grid size={{ xs: 12, lg: 6 }}>
              <Card sx={{ height: '100%' }}>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Configuration
                  </Typography>
                  <Grid container spacing={2}>
                    <Grid size={{ xs: 6 }}>
                      <Typography variant="caption" color="text.secondary">Loss Threshold</Typography>
                      <Typography variant="body1" fontWeight={600}>
                        {status.config?.loss_threshold_percent}%
                      </Typography>
                    </Grid>
                    <Grid size={{ xs: 6 }}>
                      <Typography variant="caption" color="text.secondary">Required Pyramids</Typography>
                      <Typography variant="body1" fontWeight={600}>
                        {status.config?.required_pyramids_for_timer}
                      </Typography>
                    </Grid>
                    <Grid size={{ xs: 6 }}>
                      <Typography variant="caption" color="text.secondary">Post-Pyramids Wait</Typography>
                      <Typography variant="body1" fontWeight={600}>
                        {status.config?.post_pyramids_wait_minutes} min
                      </Typography>
                    </Grid>
                    <Grid size={{ xs: 6 }}>
                      <Typography variant="caption" color="text.secondary">Max Winners to Combine</Typography>
                      <Typography variant="body1" fontWeight={600}>
                        {status.config?.max_winners_to_combine}
                      </Typography>
                    </Grid>
                    <Grid size={{ xs: 6 }}>
                      <Typography variant="caption" color="text.secondary">Loss Circuit Breaker</Typography>
                      <Typography variant="body1" fontWeight={600}>
                        ${safeToFixed(metrics.maxLoss)}
                      </Typography>
                    </Grid>
                    <Grid size={{ xs: 6 }}>
                      <Typography variant="caption" color="text.secondary">Max Open Positions</Typography>
                      <Typography variant="body1" fontWeight={600}>
                        {status.config?.max_open_positions_global || '-'}
                      </Typography>
                    </Grid>
                  </Grid>
                </CardContent>
              </Card>
            </Grid>

            {/* At-Risk Positions */}
            <Grid size={{ xs: 12 }}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    At-Risk Positions
                  </Typography>
                  {status.at_risk_positions && status.at_risk_positions.length > 0 ? (
                    <TableContainer component={Paper} variant="outlined">
                      <Table size="small">
                        <TableHead>
                          <TableRow>
                            <TableCell>Symbol</TableCell>
                            <TableCell align="right">Loss %</TableCell>
                            <TableCell align="right">Loss $</TableCell>
                            <TableCell>Timer</TableCell>
                            <TableCell>Status</TableCell>
                          </TableRow>
                        </TableHead>
                        <TableBody>
                          {status.at_risk_positions.map((pos) => (
                            <TableRow
                              key={pos.id}
                              sx={{
                                backgroundColor: pos.is_selected ? 'action.selected' : 'inherit',
                                '&:hover': { backgroundColor: 'action.hover' }
                              }}
                            >
                              <TableCell>
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                  {pos.symbol}
                                  {pos.is_selected && (
                                    <Chip label="Selected" color="error" size="small" />
                                  )}
                                </Box>
                              </TableCell>
                              <TableCell align="right">
                                <Typography color="error.main" fontWeight={600}>
                                  {safeToFixed(pos.unrealized_pnl_percent)}%
                                </Typography>
                              </TableCell>
                              <TableCell align="right">
                                <Typography color="error.main">
                                  ${safeToFixed(pos.unrealized_pnl_usd)}
                                </Typography>
                              </TableCell>
                              <TableCell>
                                {pos.timer_status === 'countdown' && pos.timer_remaining_minutes !== null ? (
                                  <Chip
                                    icon={<TimerIcon />}
                                    label={`${pos.timer_remaining_minutes}m`}
                                    color="warning"
                                    size="small"
                                  />
                                ) : pos.timer_status === 'expired' ? (
                                  <Chip label="Expired" color="error" size="small" />
                                ) : (
                                  <Chip label="Inactive" color="default" size="small" />
                                )}
                              </TableCell>
                              <TableCell>
                                {pos.risk_blocked ? (
                                  <Chip label="Blocked" color="error" size="small" />
                                ) : pos.is_eligible ? (
                                  <Chip label="Eligible" color="success" size="small" />
                                ) : (
                                  <Chip label="Not Eligible" color="default" size="small" />
                                )}
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </TableContainer>
                  ) : (
                    <Box sx={{ textAlign: 'center', py: 3 }}>
                      <CheckCircleIcon sx={{ fontSize: 32, color: 'success.main', mb: 1 }} />
                      <Typography variant="body2" color="text.secondary">
                        No positions currently at risk
                      </Typography>
                    </Box>
                  )}
                </CardContent>
              </Card>
            </Grid>

            {/* Recent Actions */}
            <Grid size={{ xs: 12 }}>
              <Card>
                <CardContent>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                    <Typography variant="h6">
                      Recent Offsets
                    </Typography>
                    <Box sx={{ display: 'flex', gap: 0.5 }}>
                      <IconButton
                        size="small"
                        onClick={() => setActionsView('timeline')}
                        color={actionsView === 'timeline' ? 'primary' : 'default'}
                        sx={{ bgcolor: actionsView === 'timeline' ? 'action.selected' : 'transparent' }}
                      >
                        <TimelineIcon fontSize="small" />
                      </IconButton>
                      <IconButton
                        size="small"
                        onClick={() => setActionsView('table')}
                        color={actionsView === 'table' ? 'primary' : 'default'}
                        sx={{ bgcolor: actionsView === 'table' ? 'action.selected' : 'transparent' }}
                      >
                        <ViewListIcon fontSize="small" />
                      </IconButton>
                    </Box>
                  </Box>

                  {status.recent_actions && status.recent_actions.length > 0 ? (
                    actionsView === 'timeline' ? (
                      <Timeline
                        items={status.recent_actions.map((action): TimelineItem => ({
                          id: action.id,
                          timestamp: action.timestamp,
                          title: `Offset ${action.loser_symbol}`,
                          description: `Closed $${safeToFixed(Math.abs(safeNumber(action.loser_pnl_usd)))} loss using ${action.winners_count} winner(s)`,
                          type: 'success',
                          metadata: {
                            'Action': action.action_type,
                            'Loss': `$${safeToFixed(Math.abs(safeNumber(action.loser_pnl_usd)))}`,
                            'Winners': action.winners_count
                          }
                        }))}
                        maxItems={10}
                        compact={false}
                      />
                    ) : (
                      <TableContainer component={Paper} variant="outlined">
                        <Table size="small">
                          <TableHead>
                            <TableRow>
                              <TableCell>Time</TableCell>
                              <TableCell>Loser</TableCell>
                              <TableCell align="right">Loss</TableCell>
                              <TableCell align="center">Winners</TableCell>
                              <TableCell>Action</TableCell>
                            </TableRow>
                          </TableHead>
                          <TableBody>
                            {status.recent_actions.map((action) => (
                              <TableRow key={action.id}>
                                <TableCell sx={{ fontSize: '0.8rem' }}>
                                  {formatTimestamp(action.timestamp)}
                                </TableCell>
                                <TableCell sx={{ fontWeight: 600 }}>{action.loser_symbol}</TableCell>
                                <TableCell align="right" sx={{ color: 'error.main' }}>
                                  ${safeToFixed(Math.abs(safeNumber(action.loser_pnl_usd)))}
                                </TableCell>
                                <TableCell align="center">{action.winners_count}</TableCell>
                                <TableCell>
                                  <Chip label={action.action_type} color="info" size="small" />
                                </TableCell>
                              </TableRow>
                            ))}
                          </TableBody>
                        </Table>
                      </TableContainer>
                    )
                  ) : (
                    <Box sx={{ textAlign: 'center', py: 3 }}>
                      <Typography variant="body2" color="text.secondary">
                        No recent offsets recorded
                      </Typography>
                    </Box>
                  )}
                </CardContent>
              </Card>
            </Grid>
          </Grid>
        </>
      )}

      {/* Offset Preview Dialog */}
      <OffsetPreviewDialog
        open={offsetPreviewOpen}
        onClose={() => {
          setOffsetPreviewOpen(false);
          setOffsetPreviewData(null);
        }}
        onConfirm={handleExecuteOffset}
        data={offsetPreviewData}
        loading={executingOffset}
      />
    </Box>
  );
};

export default RiskPage;
