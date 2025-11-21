import React from 'react';
import { Card, CardContent, Typography, Box } from '@mui/material';

interface PnlCardProps {
  pnl: number | null;
}

const PnlCard: React.FC<PnlCardProps> = ({ pnl }) => {
  const pnlColor = pnl === null ? 'text.secondary' : (pnl >= 0 ? 'success.main' : 'error.main');

  return (
    <Card>
      <CardContent>
        <Typography variant="h6" component="div">
          Total PnL
        </Typography>
        <Box sx={{ mt: 2 }}>
          <Typography variant="h4" sx={{ color: pnlColor }}>
            {pnl !== null ? `$${pnl.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : 'Loading...'}
          </Typography>
        </Box>
      </CardContent>
    </Card>
  );
};

export default PnlCard;
