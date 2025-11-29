import React, { useEffect } from 'react';
import { Box, Typography, Button, Paper, Grid, Chip, CircularProgress, Alert } from '@mui/material';
import useRiskStore from '../store/riskStore';

const RiskEnginePage: React.FC = () => {
  const { status, loading, error, fetchStatus, runEvaluation, blockGroup, unblockGroup, skipGroup } = useRiskStore();

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 5000);
    return () => clearInterval(interval);
  }, [fetchStatus]);

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
        {/* Status Panel */}
        <Grid size={{ xs: 12, md: 6 }}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>Current Risk Status</Typography>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                <Box display="flex" alignItems="center">
                    <Typography variant="subtitle1" sx={{ mr: 1 }}>Engine Status:</Typography>
                    <Chip 
                        label={status?.risk_engine_running ? "Monitoring" : "Idle"} 
                        color={status?.risk_engine_running ? "success" : "default"} 
                        size="small" 
                    />
                </Box>
                
                {status?.identified_loser ? (
                    <>
                        <Typography variant="subtitle1" color="error" sx={{ mt: 2 }}>Identified Loser:</Typography>
                        <Paper variant="outlined" sx={{ p: 2, bgcolor: '#fff5f5' }}>
                            <Typography><strong>Symbol:</strong> {status.identified_loser.symbol}</Typography>
                            <Typography><strong>Unrealized PnL:</strong> ${status.identified_loser.unrealized_pnl_usd.toFixed(2)} ({status.identified_loser.unrealized_pnl_percent.toFixed(2)}%)</Typography>
                            {status.identified_loser.risk_timer_expires && (
                                <Typography sx={{ mt: 1 }}>
                                    <strong>Risk Timer:</strong> {new Date(status.identified_loser.risk_timer_expires) <= new Date() 
                                        ? <span style={{ color: 'red' }}>Active (Expired)</span> 
                                        : `Expires at ${new Date(status.identified_loser.risk_timer_expires).toLocaleTimeString()}`}
                                </Typography>
                            )}
                            <Box sx={{ mt: 1 }}>
                                <Chip 
                                    label={status.identified_loser.risk_blocked ? "Blocked" : "Active"} 
                                    color={status.identified_loser.risk_blocked ? "error" : "success"} 
                                    size="small" 
                                    sx={{ mr: 1 }}
                                />
                                {status.identified_loser.risk_skip_once && <Chip label="Skip Once" color="warning" size="small" />}
                            </Box>
                            <Box sx={{ mt: 2 }}>
                                <Button 
                                    size="small" 
                                    variant="outlined" 
                                    color="warning" 
                                    onClick={() => skipGroup(status.identified_loser!.id)}
                                    sx={{ mr: 1 }}
                                >
                                    Skip Once
                                </Button>
                                {status.identified_loser.risk_blocked ? (
                                    <Button size="small" variant="outlined" color="success" onClick={() => unblockGroup(status.identified_loser!.id)}>Unblock</Button>
                                ) : (
                                    <Button size="small" variant="outlined" color="error" onClick={() => blockGroup(status.identified_loser!.id)}>Block</Button>
                                )}
                            </Box>
                        </Paper>
                    </>
                ) : (
                    <Typography sx={{ mt: 2, fontStyle: 'italic' }}>No losing positions currently meet the criteria for offset.</Typography>
                )}

                {status?.identified_winners && status.identified_winners.length > 0 && (
                     <>
                        <Typography variant="subtitle1" color="success" sx={{ mt: 2 }}>Available Winners:</Typography>
                        {status.identified_winners.map((w) => (
                            <Typography key={w.id} variant="body2">
                                • {w.symbol} (Profit: ${w.unrealized_pnl_usd.toFixed(2)})
                            </Typography>
                        ))}
                        <Typography sx={{ mt: 1, fontWeight: 'bold' }}>
                            Required Offset: ${status.required_offset_usd.toFixed(2)}
                        </Typography>
                     </>
                )}
            </Box>
          </Paper>
        </Grid>

        {/* Actions Panel */}
        <Grid size={{ xs: 12, md: 6 }}>
          <Paper sx={{ p: 3 }}>
             <Typography variant="h6" gutterBottom>Actions</Typography>
             <Button 
                variant="contained" 
                color="primary" 
                onClick={runEvaluation}
                disabled={loading}
            >
                Run Evaluation Now
             </Button>
             <Typography variant="caption" display="block" sx={{ mt: 1 }}>
                 Manually triggers the risk engine cycle immediately.
             </Typography>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};

export default RiskEnginePage;
