import React from 'react';
import { Card, CardContent, Typography, Box, Divider, Grid } from '@mui/material';

interface PnlCardProps {
  pnl: number | null;
  realizedPnl?: number | null;
  unrealizedPnl?: number | null;
}

const PnlCard: React.FC<PnlCardProps> = ({ pnl, realizedPnl, unrealizedPnl }) => {
  const pnlColor = pnl === null ? 'text.secondary' : (pnl >= 0 ? 'success.main' : 'error.main');
  const realizedColor = (realizedPnl || 0) >= 0 ? 'success.main' : 'error.main';
  const unrealizedColor = (unrealizedPnl || 0) >= 0 ? 'success.main' : 'error.main';

  const formatCurrency = (val: number | null | undefined) => {
      if (val === null || val === undefined) return 'Loading...';
      return `$${val.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  };

  return (
    <Card>
      <CardContent>
        <Typography variant="h6" component="div">
          Total PnL
        </Typography>
        <Box sx={{ mt: 1, mb: 2 }}>
          <Typography variant="h4" sx={{ color: pnlColor }}>
            {formatCurrency(pnl)}
          </Typography>
        </Box>
        
        {(realizedPnl !== undefined || unrealizedPnl !== undefined) && (
            <>
                <Divider sx={{ my: 1 }} />
                <Grid container spacing={1}>
                    <Grid size={{ xs: 6 }}>
                        <Typography variant="caption" color="text.secondary">Realized (Banked)</Typography>
                        <Typography variant="body1" sx={{ color: realizedColor, fontWeight: 'bold' }}>
                            {formatCurrency(realizedPnl)}
                        </Typography>
                    </Grid>
                    <Grid size={{ xs: 6 }}>
                         <Typography variant="caption" color="text.secondary">Unrealized (Floating)</Typography>
                        <Typography variant="body1" sx={{ color: unrealizedColor, fontWeight: 'bold' }}>
                            {formatCurrency(unrealizedPnl)}
                        </Typography>
                    </Grid>
                </Grid>
            </>
        )}
      </CardContent>
    </Card>
  );
};

export default PnlCard;
