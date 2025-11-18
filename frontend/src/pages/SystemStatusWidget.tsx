import React from 'react';
import { Card, CardContent, Typography } from '@mui/material';
import { useSystemStore } from '../store/systemStore';

const SystemStatusWidget: React.FC = () => {
  const { engineStatus, riskEngineStatus, lastWebhookTimestamp } = useSystemStore();
  return (
    <Card>
      <CardContent>
        <Typography variant="h6">System Status</Typography>
        <Typography>Engine: {engineStatus}</Typography>
        <Typography>Risk Engine: {riskEngineStatus}</Typography>
        <Typography>Last Signal: {lastWebhookTimestamp}</Typography>
      </CardContent>
    </Card>
  );
};

export default SystemStatusWidget;
