import React from 'react';
import { Card, CardContent, Typography } from '@mui/material';
import { useDataStore } from '../store/dataStore';

const PnlCard: React.FC = () => {
  const { pnlMetrics } = useDataStore();
  return (
    <Card>
      <CardContent>
        <Typography>Unrealized PNL: ${pnlMetrics.unrealized_pnl}</Typography>
        <Typography>Realized PNL: ${pnlMetrics.realized_pnl}</Typography>
        <Typography>Total PNL: ${pnlMetrics.total_pnl}</Typography>
      </CardContent>
    </Card>
  );
};

export default PnlCard;
