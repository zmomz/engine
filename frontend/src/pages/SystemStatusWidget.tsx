import React from 'react';
import { Card, CardContent, Typography, Chip, Box } from '@mui/material';
import { useSystemStore } from '../store/systemStore';

const SystemStatusWidget: React.FC = () => {
  const { engineStatus, riskEngineStatus, lastWebhookTimestamp } = useSystemStore();

  const getEngineStatusColor = (status: string) => {
    switch (status) {
      case 'Running':
        return 'success';
      case 'Stopped':
        return 'error';
      case 'Error':
        return 'error';
      default:
        return 'default';
    }
  };

  const getRiskEngineStatusColor = (status: string) => {
    switch (status) {
      case 'Monitoring':
        return 'info';
      case 'Paused':
        return 'warning';
      case 'Error':
        return 'error';
      default:
        return 'default';
    }
  };

  return (
    <Card>
      <CardContent>
        <Typography variant="h6">System Status</Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
          <Typography sx={{ mr: 1 }}>Engine:</Typography>
          <Chip
            label={engineStatus}
            color={getEngineStatusColor(engineStatus)}
            data-testid="engine-status-chip"
            data-color={getEngineStatusColor(engineStatus)}
          />
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
          <Typography sx={{ mr: 1 }}>Risk Engine:</Typography>
          <Chip
            label={riskEngineStatus}
            color={getRiskEngineStatusColor(riskEngineStatus)}
            data-testid="risk-engine-status-chip"
            data-color={getRiskEngineStatusColor(riskEngineStatus)}
          />
        </Box>
        <Typography>Last Signal: {lastWebhookTimestamp}</Typography>
      </CardContent>
    </Card>
  );
};

export default SystemStatusWidget;