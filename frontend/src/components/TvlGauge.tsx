import React from 'react';
import { Card, CardContent, Typography, Box } from '@mui/material';

interface TvlGaugeProps {
  tvl: number | null;
}

const TvlGauge: React.FC<TvlGaugeProps> = ({ tvl }) => {
  return (
    <Card>
      <CardContent>
        <Typography variant="h6" component="div">
          Total Value Locked
        </Typography>
        <Box sx={{ mt: 2 }}>
          <Typography variant="h4" color="primary">
            {tvl !== null ? `$${tvl.toLocaleString()}` : 'Loading...'}
          </Typography>
        </Box>
      </CardContent>
    </Card>
  );
};

export default TvlGauge;
