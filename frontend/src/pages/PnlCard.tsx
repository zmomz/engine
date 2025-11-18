import React from 'react';
import { Card, CardContent, Typography } from '@mui/material';
import { useDataStore } from '../store/dataStore';

const PnlCard: React.FC = () => {
  const { pnlMetrics } = useDataStore();

  const getPnlColor = (value: number) => {
    if (value > 0) {
      return 'green';
    } else if (value < 0) {
      return 'red';
    } else {
      return 'inherit';
    }
  };

  return (
    <Card>
      <CardContent>
        <Typography
          data-testid="unrealized-pnl"
          style={{ color: getPnlColor(pnlMetrics.unrealized_pnl) }}
        >
          Unrealized PNL: ${pnlMetrics.unrealized_pnl}
        </Typography>
        <Typography
          data-testid="realized-pnl"
          style={{ color: getPnlColor(pnlMetrics.realized_pnl) }}
        >
          Realized PNL: ${pnlMetrics.realized_pnl}
        </Typography>
        <Typography
          data-testid="total-pnl"
          style={{ color: getPnlColor(pnlMetrics.total_pnl) }}
        >
          Total PNL: ${pnlMetrics.total_pnl}
        </Typography>
      </CardContent>
    </Card>
  );
};

export default PnlCard;