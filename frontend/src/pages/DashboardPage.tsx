import React from 'react';
import { Grid, Typography } from '@mui/material';
import PoolUsageWidget from './PoolUsageWidget';
import SystemStatusWidget from './SystemStatusWidget';
import PnlCard from './PnlCard';

const DashboardPage: React.FC = () => {
  return (
    <div>
      <Typography variant="h4" gutterBottom>
        Dashboard
      </Typography>
      <Grid container spacing={3}>
        <Grid item xs={12} md={4}>
          <PoolUsageWidget />
        </Grid>
        <Grid item xs={12} md={4}>
          <SystemStatusWidget />
        </Grid>
        <Grid item xs={12} md={4}>
          <PnlCard />
        </Grid>
        <Grid item xs={12}>
          <EquityCurveChart />
        </Grid>
      </Grid>
    </div>
  );
};

export default DashboardPage;
