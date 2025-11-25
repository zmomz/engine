import React, { useEffect } from 'react';
import { Box, Typography, Button, Card, CardContent, Grid, Chip } from '@mui/material';
import useRiskStore from '../store/riskStore';
import useConfirmStore from '../store/confirmStore';

const RiskPage: React.FC = () => {
  const { status, loading, error, fetchStatus, runEvaluation, blockGroup, unblockGroup, skipGroup } = useRiskStore();

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 5000); // Poll every 5 seconds
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

  return (
    <Box sx={{ flexGrow: 1, p: 3 }}>
      <Typography variant="h4" gutterBottom>
        Risk Control Panel
      </Typography>
      {loading && <Typography>Loading risk status...</Typography>}
      {error && <Typography color="error">Error: {error}</Typography>}

      {status && (
        <Grid container spacing={3}>
          <Grid size={{ xs: 12, md: 6 }}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Risk Engine Status
                </Typography>
                <Typography variant="body1" component="div">Running: <Chip label={status.risk_engine_running ? 'Yes' : 'No'} color={status.risk_engine_running ? 'success' : 'error'} size="small" /></Typography>
                <Typography variant="subtitle1" sx={{ mt: 2 }}>Configuration:</Typography>
                {status.config && Object.entries(status.config).map(([key, value]) => (
                  <Typography variant="body2" key={key}><strong>{key}:</strong> {String(value)}</Typography>
                ))}
                <Button
                  variant="contained"
                  color="primary"
                  onClick={handleRunEvaluation}
                  sx={{ mt: 2 }}
                  disabled={loading}
                >
                  Run Risk Evaluation Now
                </Button>
              </CardContent>
            </Card>
          </Grid>

          <Grid size={{ xs: 12, md: 6 }}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Identified Positions for Offset
                </Typography>
                {status.identified_loser ? (
                  <Box sx={{ mb: 2 }}>
                    <Typography variant="subtitle1" color="error.main">Loser:</Typography>
                    <Typography variant="body1">Symbol: {status.identified_loser.symbol}</Typography>
                    <Typography variant="body1">PnL %: {status.identified_loser.unrealized_pnl_percent?.toFixed(2)}%</Typography>
                    <Typography variant="body1">PnL $: ${status.identified_loser.unrealized_pnl_usd?.toFixed(2)}</Typography>
                    <Typography variant="body1" component="div">Blocked: <Chip label={status.identified_loser.risk_blocked ? 'Yes' : 'No'} color={status.identified_loser.risk_blocked ? 'warning' : 'info'} size="small" /></Typography>
                    <Typography variant="body1" component="div">Skip Once: <Chip label={status.identified_loser.risk_skip_once ? 'Yes' : 'No'} color={status.identified_loser.risk_skip_once ? 'warning' : 'info'} size="small" /></Typography>
                    <Box sx={{ mt: 1 }}>
                      {!status.identified_loser.risk_blocked ? (
                        <Button size="small" variant="outlined" color="warning" onClick={() => handleBlock(status.identified_loser!.id)} sx={{ mr: 1 }}>Block</Button>
                      ) : (
                        <Button size="small" variant="outlined" color="success" onClick={() => handleUnblock(status.identified_loser!.id)} sx={{ mr: 1 }}>Unblock</Button>
                      )}
                      {!status.identified_loser.risk_skip_once && (
                        <Button size="small" variant="outlined" color="info" onClick={() => handleSkip(status.identified_loser!.id)}>Skip Next</Button>
                      )}
                    </Box>
                  </Box>
                ) : (
                  <Typography variant="body2">No loser identified.</Typography>
                )}

                <Typography variant="subtitle1" sx={{ mt: 2 }}>Winners (to offset):</Typography>
                {status.identified_winners && status.identified_winners.length > 0 ? (
                  status.identified_winners.map((winner) => (
                    <Box key={winner.id} sx={{ mb: 1, ml: 2, borderLeft: '2px solid grey', pl: 1 }}>
                      <Typography variant="body2">Symbol: {winner.symbol}</Typography>
                      <Typography variant="body2">PnL $: ${winner.unrealized_pnl_usd?.toFixed(2)}</Typography>
                    </Box>
                  ))
                ) : (
                  <Typography variant="body2">No winners identified for offset.</Typography>
                )}

                <Typography variant="body1" sx={{ mt: 2 }}>Required Offset: <strong>${status.required_offset_usd?.toFixed(2)}</strong></Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}
    </Box>
  );
};

export default RiskPage;
