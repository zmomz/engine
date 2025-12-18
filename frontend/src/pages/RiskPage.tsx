import React, { useEffect } from 'react';
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
  Divider
} from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import CancelIcon from '@mui/icons-material/Cancel';
import TimerIcon from '@mui/icons-material/Timer';
import useRiskStore from '../store/riskStore';
import useConfirmStore from '../store/confirmStore';
import { RiskPageSkeleton } from '../components/RiskSkeleton';

const RiskPage: React.FC = () => {
  const { status, loading, error, fetchStatus, runEvaluation, blockGroup, unblockGroup, skipGroup } = useRiskStore();

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(() => fetchStatus(true), 5000);
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

  const formatTimestamp = (timestamp: string | null) => {
    if (!timestamp) return 'N/A';
    return new Date(timestamp).toLocaleString();
  };

  // Show skeleton on initial load
  if (loading && !status) {
    return <RiskPageSkeleton />;
  }

  return (
    <Box sx={{ flexGrow: 1, p: { xs: 2, sm: 3 } }}>
      <Box sx={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: { xs: 'flex-start', sm: 'center' },
        flexDirection: { xs: 'column', sm: 'row' },
        mb: 3,
        gap: 2
      }}>
        <Typography variant="h4" sx={{ fontSize: { xs: '1.5rem', sm: '2.125rem' } }}>
          Risk Control Panel
        </Typography>
        <Button
          variant="contained"
          color="primary"
          onClick={handleRunEvaluation}
          disabled={loading}
          fullWidth
          sx={{ width: { xs: '100%', sm: 'auto' } }}
        >
          Run Evaluation Now
        </Button>
      </Box>

      {loading && !status && <LinearProgress />}
      {error && <Typography color="error" sx={{ mb: 2 }}>Error: {error}</Typography>}

      {status && (
        <Grid container spacing={{ xs: 2, sm: 3 }}>
          {/* Statistics Dashboard */}
          <Grid size={{ xs: 12 }}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>Statistics</Typography>
                <Grid container spacing={2}>
                  <Grid size={{ xs: 12, sm: 4 }}>
                    <Box sx={{ textAlign: 'center' }}>
                      <Typography variant="h4" color="primary">
                        {status.recent_actions?.length || 0}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        Recent Offsets
                      </Typography>
                    </Box>
                  </Grid>
                  <Grid size={{ xs: 12, sm: 4 }}>
                    <Box sx={{ textAlign: 'center' }}>
                      <Typography variant="h4" color="error">
                        ${status.recent_actions?.reduce((sum, a) => sum + Math.abs(a.loser_pnl_usd), 0).toFixed(2) || '0.00'}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        Total Loss Offset
                      </Typography>
                    </Box>
                  </Grid>
                  <Grid size={{ xs: 12, sm: 4 }}>
                    <Box sx={{ textAlign: 'center' }}>
                      <Typography variant="h4" color="success.main">
                        {status.recent_actions?.length > 0 ? '100%' : '0%'}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        Success Rate
                      </Typography>
                    </Box>
                  </Grid>
                </Grid>
              </CardContent>
            </Card>
          </Grid>

          {/* Current Evaluation */}
          <Grid size={{ xs: 12, md: 6 }}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Current Evaluation
                </Typography>

                {status.identified_loser ? (
                  <Box>
                    <Typography variant="subtitle1" color="error.main" gutterBottom>
                      Selected Loser: {status.identified_loser.symbol}
                    </Typography>

                    <Box sx={{ mb: 2 }}>
                      <Typography variant="body2">
                        <strong>Loss:</strong> {status.identified_loser.unrealized_pnl_percent.toFixed(2)}%
                        (${status.identified_loser.unrealized_pnl_usd.toFixed(2)})
                      </Typography>
                      <Typography variant="body2">
                        <strong>Age:</strong> {status.identified_loser.age_minutes} minutes
                      </Typography>
                      <Typography variant="body2">
                        <strong>Pyramids:</strong> {status.identified_loser.pyramid_count}/{status.identified_loser.max_pyramids}
                      </Typography>
                      <Typography variant="body2" component="div">
                        <strong>Timer:</strong>{' '}
                        {status.identified_loser.timer_status === 'active' ? (
                          <Chip
                            icon={<TimerIcon />}
                            label={`${status.identified_loser.timer_remaining_minutes} min`}
                            color="warning"
                            size="small"
                          />
                        ) : status.identified_loser.timer_status === 'expired' ? (
                          <Chip label="Expired" color="error" size="small" />
                        ) : (
                          <Chip label="Inactive" color="default" size="small" />
                        )}
                      </Typography>
                      <Typography variant="body2" component="div">
                        <strong>Eligible:</strong>{' '}
                        {status.identified_loser.pyramids_reached && status.identified_loser.age_filter_passed ? (
                          <CheckCircleIcon color="success" fontSize="small" />
                        ) : (
                          <CancelIcon color="error" fontSize="small" />
                        )}
                        {!status.identified_loser.pyramids_reached && ' (Pyramids not reached)'}
                        {!status.identified_loser.age_filter_passed && ' (Age filter not passed)'}
                      </Typography>
                    </Box>

                    <Divider sx={{ my: 2 }} />

                    <Typography variant="subtitle2" gutterBottom>Required Offset: ${status.required_offset_usd.toFixed(2)}</Typography>
                    <Typography variant="subtitle2" gutterBottom>Available Profit: ${status.total_available_profit.toFixed(2)}</Typography>

                    {status.projected_plan && status.projected_plan.length > 0 && (
                      <Box sx={{ mt: 2 }}>
                        <Typography variant="subtitle2" gutterBottom>Projected Offset Plan:</Typography>
                        {status.projected_plan.map((plan, idx) => (
                          <Box key={idx} sx={{ ml: 2, mb: 1 }}>
                            <Typography variant="body2">
                              • {plan.symbol}: ${plan.amount_to_close.toFixed(2)}
                              {plan.partial && ' (partial close)'}
                            </Typography>
                          </Box>
                        ))}
                      </Box>
                    )}

                    <Box sx={{ mt: 2 }}>
                      {!status.identified_loser.risk_blocked ? (
                        <Button
                          size="small"
                          variant="outlined"
                          color="warning"
                          onClick={() => handleBlock(status.identified_loser!.id)}
                          sx={{ mr: 1 }}
                        >
                          Block
                        </Button>
                      ) : (
                        <Button
                          size="small"
                          variant="outlined"
                          color="success"
                          onClick={() => handleUnblock(status.identified_loser!.id)}
                          sx={{ mr: 1 }}
                        >
                          Unblock
                        </Button>
                      )}
                      {!status.identified_loser.risk_skip_once && (
                        <Button
                          size="small"
                          variant="outlined"
                          color="info"
                          onClick={() => handleSkip(status.identified_loser!.id)}
                        >
                          Skip Next
                        </Button>
                      )}
                    </Box>
                  </Box>
                ) : (
                  <Typography variant="body2" color="text.secondary">
                    No position currently selected for offset.
                  </Typography>
                )}
              </CardContent>
            </Card>
          </Grid>

          {/* Engine Status */}
          <Grid size={{ xs: 12, md: 6 }}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Engine Status
                </Typography>
                <Typography variant="body1" component="div" sx={{ mb: 2 }}>
                  Status: <Chip
                    label={status.risk_engine_running ? 'Running' : 'Stopped'}
                    color={status.risk_engine_running ? 'success' : 'error'}
                    size="small"
                  />
                </Typography>

                <Typography variant="subtitle2" gutterBottom>Configuration:</Typography>
                <Box sx={{ ml: 2 }}>
                  <Typography variant="body2">
                    <strong>Loss Threshold:</strong> {status.config?.loss_threshold_percent}%
                  </Typography>
                  <Typography variant="body2">
                    <strong>Required Pyramids for Timer:</strong> {status.config?.required_pyramids_for_timer}
                  </Typography>
                  <Typography variant="body2">
                    <strong>Post-Pyramids Wait:</strong> {status.config?.post_pyramids_wait_minutes} min
                  </Typography>
                  <Typography variant="body2">
                    <strong>Max Winners to Combine:</strong> {status.config?.max_winners_to_combine}
                  </Typography>
                </Box>
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
                              {pos.symbol}
                              {pos.is_selected && (
                                <Chip label="Selected" color="primary" size="small" sx={{ ml: 1 }} />
                              )}
                            </TableCell>
                            <TableCell align="right">
                              {pos.unrealized_pnl_percent.toFixed(2)}%
                            </TableCell>
                            <TableCell align="right">
                              ${pos.unrealized_pnl_usd.toFixed(2)}
                            </TableCell>
                            <TableCell>
                              {pos.timer_status === 'countdown' && pos.timer_remaining_minutes !== null ? (
                                <Chip
                                  icon={<TimerIcon />}
                                  label={`${pos.timer_remaining_minutes} min`}
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
                  <Typography variant="body2" color="text.secondary">
                    No positions currently at risk.
                  </Typography>
                )}
              </CardContent>
            </Card>
          </Grid>

          {/* Recent Actions */}
          <Grid size={{ xs: 12 }}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Recent Actions
                </Typography>
                {status.recent_actions && status.recent_actions.length > 0 ? (
                  <TableContainer component={Paper} variant="outlined">
                    <Table size="small">
                      <TableHead>
                        <TableRow>
                          <TableCell>Timestamp</TableCell>
                          <TableCell>Loser</TableCell>
                          <TableCell align="right">Loss $</TableCell>
                          <TableCell align="center">Winners Used</TableCell>
                          <TableCell>Action</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {status.recent_actions.map((action) => (
                          <TableRow key={action.id}>
                            <TableCell>{formatTimestamp(action.timestamp)}</TableCell>
                            <TableCell>{action.loser_symbol}</TableCell>
                            <TableCell align="right">${Math.abs(action.loser_pnl_usd).toFixed(2)}</TableCell>
                            <TableCell align="center">{action.winners_count}</TableCell>
                            <TableCell>
                              <Chip
                                label={action.action_type}
                                color="info"
                                size="small"
                              />
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                ) : (
                  <Typography variant="body2" color="text.secondary">
                    No recent actions recorded.
                  </Typography>
                )}
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}
    </Box>
  );
};

export default RiskPage;
