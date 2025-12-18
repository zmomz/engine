import React, { useEffect } from 'react';
import { Box, Typography, Button, Paper, Grid, Chip, CircularProgress, Alert, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Divider } from '@mui/material';
import { PlayArrow, SkipNext, Block, CheckCircle, Warning, Timer } from '@mui/icons-material';
import useRiskStore from '../store/riskStore';

const RiskEnginePage: React.FC = () => {
  const { status, loading, error, fetchStatus, runEvaluation, blockGroup, unblockGroup, skipGroup } = useRiskStore();

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(() => fetchStatus(true), 5000);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  const getTimerStatusChip = (timerStatus: string, remainingMinutes: number | null) => {
    switch (timerStatus) {
      case 'expired':
        return <Chip icon={<Warning />} label="Timer Expired" color="error" size="small" />;
      case 'active':
        return <Chip icon={<Timer />} label={`${remainingMinutes?.toFixed(0) || 0}m remaining`} color="warning" size="small" />;
      case 'waiting_pyramids':
        return <Chip label="Waiting for Pyramids" color="info" size="small" />;
      case 'waiting_threshold':
        return <Chip label="Above Threshold" color="default" size="small" />;
      default:
        return <Chip label={timerStatus} size="small" />;
    }
  };

  if (loading && !status) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" gutterBottom>Risk Engine Panel</Typography>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      <Grid container spacing={3}>
        {/* Identified Loser Panel */}
        <Grid size={{ xs: 12, md: 6 }}>
          <Paper sx={{ p: 3, height: '100%' }}>
            <Typography variant="h6" gutterBottom color="error">Identified Loser</Typography>
            {status?.identified_loser ? (
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                <Paper variant="outlined" sx={{ p: 2, bgcolor: '#fff5f5' }}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                    <Typography variant="h6">{status.identified_loser.symbol}</Typography>
                    <Box>
                      <Chip
                        label={status.identified_loser.risk_blocked ? "Blocked" : "Active"}
                        color={status.identified_loser.risk_blocked ? "error" : "success"}
                        size="small"
                        sx={{ mr: 1 }}
                      />
                      {status.identified_loser.risk_skip_once && <Chip label="Skip Once" color="warning" size="small" />}
                    </Box>
                  </Box>

                  <Typography color="error.main" sx={{ fontSize: '1.5rem', fontWeight: 'bold' }}>
                    ${status.identified_loser.unrealized_pnl_usd.toFixed(2)} ({status.identified_loser.unrealized_pnl_percent.toFixed(2)}%)
                  </Typography>

                  <Divider sx={{ my: 1.5 }} />

                  <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1 }}>
                    <Typography variant="body2"><strong>Pyramids:</strong> {status.identified_loser.pyramid_count}/{status.identified_loser.max_pyramids}</Typography>
                    <Typography variant="body2"><strong>Age:</strong> {status.identified_loser.age_minutes.toFixed(0)} min</Typography>
                    <Typography variant="body2"><strong>Pyramids Met:</strong> {status.identified_loser.pyramids_reached ? 'Yes' : 'No'}</Typography>
                    <Typography variant="body2"><strong>Age Filter:</strong> {status.identified_loser.age_filter_passed ? 'Passed' : 'Pending'}</Typography>
                  </Box>

                  <Box sx={{ mt: 2 }}>
                    <Typography variant="body2" sx={{ mb: 1 }}><strong>Timer Status:</strong></Typography>
                    {getTimerStatusChip(status.identified_loser.timer_status, status.identified_loser.timer_remaining_minutes)}
                    {status.identified_loser.risk_timer_expires && (
                      <Typography variant="caption" display="block" sx={{ mt: 0.5 }}>
                        Expires: {new Date(status.identified_loser.risk_timer_expires).toLocaleString()}
                      </Typography>
                    )}
                  </Box>

                  <Box sx={{ mt: 2, display: 'flex', gap: 1 }}>
                    <Button
                      size="small"
                      variant="outlined"
                      color="warning"
                      startIcon={<SkipNext />}
                      onClick={() => skipGroup(status.identified_loser!.id)}
                    >
                      Skip Once
                    </Button>
                    {status.identified_loser.risk_blocked ? (
                      <Button size="small" variant="outlined" color="success" startIcon={<CheckCircle />} onClick={() => unblockGroup(status.identified_loser!.id)}>Unblock</Button>
                    ) : (
                      <Button size="small" variant="outlined" color="error" startIcon={<Block />} onClick={() => blockGroup(status.identified_loser!.id)}>Block</Button>
                    )}
                  </Box>
                </Paper>
              </Box>
            ) : (
              <Box sx={{ textAlign: 'center', py: 4 }}>
                <CheckCircle sx={{ fontSize: 48, color: 'success.main', mb: 1 }} />
                <Typography color="text.secondary">No losing positions currently meet the criteria for offset.</Typography>
              </Box>
            )}
          </Paper>
        </Grid>

        {/* Available Winners Panel */}
        <Grid size={{ xs: 12, md: 6 }}>
          <Paper sx={{ p: 3, height: '100%' }}>
            <Typography variant="h6" gutterBottom color="success.main">Available Winners</Typography>
            {status?.identified_winners && status.identified_winners.length > 0 ? (
              <>
                <TableContainer>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Symbol</TableCell>
                        <TableCell align="right">Unrealized Profit</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {status.identified_winners.map((w) => (
                        <TableRow key={w.id}>
                          <TableCell>{w.symbol}</TableCell>
                          <TableCell align="right" sx={{ color: 'success.main' }}>${w.unrealized_pnl_usd.toFixed(2)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
                <Box sx={{ mt: 2, p: 2, bgcolor: 'grey.100', borderRadius: 1 }}>
                  <Typography variant="body2"><strong>Required Offset:</strong> ${status.required_offset_usd.toFixed(2)}</Typography>
                  <Typography variant="body2"><strong>Total Available:</strong> ${status.total_available_profit.toFixed(2)}</Typography>
                </Box>
              </>
            ) : (
              <Box sx={{ textAlign: 'center', py: 4 }}>
                <Typography color="text.secondary">No winning positions available for offset.</Typography>
              </Box>
            )}
          </Paper>
        </Grid>

        {/* At-Risk Positions Panel */}
        <Grid size={{ xs: 12 }}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>At-Risk Positions</Typography>
            {status?.at_risk_positions && status.at_risk_positions.length > 0 ? (
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Symbol</TableCell>
                      <TableCell align="right">PnL USD</TableCell>
                      <TableCell align="right">PnL %</TableCell>
                      <TableCell>Timer Status</TableCell>
                      <TableCell>Status</TableCell>
                      <TableCell align="center">Actions</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {status.at_risk_positions.map((pos) => (
                      <TableRow key={pos.id} sx={{ bgcolor: pos.is_selected ? 'warning.light' : 'inherit' }}>
                        <TableCell>
                          {pos.symbol}
                          {pos.is_selected && <Chip label="Selected" size="small" color="warning" sx={{ ml: 1 }} />}
                        </TableCell>
                        <TableCell align="right" sx={{ color: 'error.main' }}>${pos.unrealized_pnl_usd.toFixed(2)}</TableCell>
                        <TableCell align="right" sx={{ color: 'error.main' }}>{pos.unrealized_pnl_percent.toFixed(2)}%</TableCell>
                        <TableCell>{getTimerStatusChip(pos.timer_status, pos.timer_remaining_minutes)}</TableCell>
                        <TableCell>
                          {pos.risk_blocked ? (
                            <Chip label="Blocked" color="error" size="small" />
                          ) : pos.is_eligible ? (
                            <Chip label="Eligible" color="success" size="small" />
                          ) : (
                            <Chip label="Not Eligible" color="default" size="small" />
                          )}
                        </TableCell>
                        <TableCell align="center">
                          {pos.risk_blocked ? (
                            <Button size="small" variant="text" color="success" onClick={() => unblockGroup(pos.id)}>Unblock</Button>
                          ) : (
                            <Button size="small" variant="text" color="error" onClick={() => blockGroup(pos.id)}>Block</Button>
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            ) : (
              <Typography color="text.secondary" sx={{ textAlign: 'center', py: 2 }}>No at-risk positions.</Typography>
            )}
          </Paper>
        </Grid>

        {/* Recent Actions Panel */}
        <Grid size={{ xs: 12, md: 6 }}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>Recent Risk Actions</Typography>
            {status?.recent_actions && status.recent_actions.length > 0 ? (
              <TableContainer sx={{ maxHeight: 300 }}>
                <Table size="small" stickyHeader>
                  <TableHead>
                    <TableRow>
                      <TableCell>Time</TableCell>
                      <TableCell>Loser</TableCell>
                      <TableCell align="right">Loss</TableCell>
                      <TableCell>Action</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {status.recent_actions.map((action) => (
                      <TableRow key={action.id}>
                        <TableCell>{action.timestamp ? new Date(action.timestamp).toLocaleString() : 'N/A'}</TableCell>
                        <TableCell>{action.loser_symbol}</TableCell>
                        <TableCell align="right" sx={{ color: 'error.main' }}>${action.loser_pnl_usd.toFixed(2)}</TableCell>
                        <TableCell>
                          <Chip
                            label={`${action.action_type} (${action.winners_count} winners)`}
                            size="small"
                            color={action.action_type === 'offset_executed' ? 'success' : 'default'}
                          />
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            ) : (
              <Typography color="text.secondary" sx={{ textAlign: 'center', py: 2 }}>No recent risk actions.</Typography>
            )}
          </Paper>
        </Grid>

        {/* Actions Panel */}
        <Grid size={{ xs: 12, md: 6 }}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>Manual Actions</Typography>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <Box>
                <Button
                  variant="contained"
                  color="primary"
                  startIcon={<PlayArrow />}
                  onClick={runEvaluation}
                  disabled={loading}
                  fullWidth
                >
                  Run Evaluation Now
                </Button>
                <Typography variant="caption" display="block" sx={{ mt: 0.5 }}>
                  Manually triggers the risk engine evaluation cycle immediately.
                </Typography>
              </Box>
            </Box>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};

export default RiskEnginePage;
