import React, { useEffect } from 'react';
import { Box, Grid, Typography } from '@mui/material';
import useEngineStore, { startEngineDataPolling, stopEngineDataPolling } from '../store/engineStore';
import TvlGauge from '../components/TvlGauge';
import PnlCard from '../components/PnlCard';
import ActiveGroupsWidget from '../components/ActiveGroupsWidget';
import EquityCurveChart from '../components/EquityCurveChart';

const DashboardPage: React.FC = () => {
  const { tvl, pnl, activeGroupsCount, fetchEngineData } = useEngineStore();

  useEffect(() => {
    // Fetch data immediately on mount
    fetchEngineData();
    // Start polling
    startEngineDataPolling();

    // Stop polling on unmount
    return () => {
      stopEngineDataPolling();
    };
  }, [fetchEngineData]);

  return (
    <Box sx={{ flexGrow: 1, p: 3 }}>
      <Typography variant="h4" gutterBottom>
        Dashboard
      </Typography>
      <Grid container spacing={3}>
        <Grid size={{ xs: 12, sm: 6, md: 4 }}>
            <TvlGauge tvl={tvl} />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 4 }}>
          <PnlCard pnl={pnl} />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 4 }}>
          <ActiveGroupsWidget count={activeGroupsCount} />
        </Grid>
        <Grid size={{ xs: 12 }}>
          <EquityCurveChart />
        </Grid>
      </Grid>
    </Box>
  );
};

export default DashboardPage;
