import React from 'react';
import { Card, CardContent, Typography, LinearProgress, Box } from '@mui/material';
import { useDataStore } from '../store/dataStore';

const PoolUsageWidget: React.FC = () => {
  const { poolUsage } = useDataStore();
  const progress = poolUsage.max > 0 ? (poolUsage.active / poolUsage.max) * 100 : 0;

  return (
    <Card>
      <CardContent>
        <Typography variant="h6">Pool Usage</Typography>
        <Typography variant="h4">
          {poolUsage.active} / {poolUsage.max}
        </Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', mt: 2 }}>
          <Box sx={{ width: '100%', mr: 1 }}>
            <LinearProgress variant="determinate" value={progress} />
          </Box>
          <Box sx={{ minWidth: 35 }}>
            <Typography variant="body2" color="text.secondary">{`${Math.round(
              progress
            )}%`}</Typography>
          </Box>
        </Box>
      </CardContent>
    </Card>
  );
};

export default PoolUsageWidget;