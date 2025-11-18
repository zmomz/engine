import React from 'react';
import { Card, CardContent, Typography } from '@mui/material';
import { useDataStore } from '../store/dataStore';

const PoolUsageWidget: React.FC = () => {
  const { poolUsage } = useDataStore();
  return (
    <Card>
      <CardContent>
        <Typography variant="h6">Pool Usage</Typography>
        <Typography variant="h4">
          {poolUsage.active} / {poolUsage.max}
        </Typography>
      </CardContent>
    </Card>
  );
};

export default PoolUsageWidget;
