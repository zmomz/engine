import React from 'react';
import { Card, CardContent, Typography, Grid } from '@mui/material';

interface WinLossWidgetProps {
  totalTrades: number | null;
  wins: number | null;
  losses: number | null;
  winRate: number | null;
}

const WinLossWidget: React.FC<WinLossWidgetProps> = ({ totalTrades, wins, losses, winRate }) => {
  return (
    <Card>
      <CardContent>
        <Typography variant="h6" component="div" gutterBottom>
          Trade Statistics
        </Typography>
        <Grid container spacing={2}>
            <Grid size={{ xs: 6 }}>
                <Typography variant="body2" color="text.secondary">Total Trades</Typography>
                <Typography variant="h6">{totalTrades ?? '-'}</Typography>
            </Grid>
            <Grid size={{ xs: 6 }}>
                <Typography variant="body2" color="text.secondary">Win Rate</Typography>
                <Typography variant="h6" color="primary.main">{winRate !== null ? `${winRate.toFixed(1)}%` : '-'}</Typography>
            </Grid>
            <Grid size={{ xs: 6 }}>
                <Typography variant="body2" color="text.secondary">Wins</Typography>
                <Typography variant="h6" color="success.main">{wins ?? '-'}</Typography>
            </Grid>
            <Grid size={{ xs: 6 }}>
                <Typography variant="body2" color="text.secondary">Losses</Typography>
                <Typography variant="h6" color="error.main">{losses ?? '-'}</Typography>
            </Grid>
        </Grid>
      </CardContent>
    </Card>
  );
};

export default WinLossWidget;
