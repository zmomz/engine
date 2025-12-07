import React, { useEffect } from 'react';
import { Box, Grid, Typography } from '@mui/material';
import useEngineStore, { startEngineDataPolling, stopEngineDataPolling } from '../store/engineStore';
import TvlGauge from '../components/TvlGauge';
import PnlCard from '../components/PnlCard';
import ActiveGroupsWidget from '../components/ActiveGroupsWidget';
import FreeUsdtCard from '../components/FreeUsdtCard';
import EquityCurveChart from '../components/EquityCurveChart';
import WinLossWidget from '../components/WinLossWidget';


const DashboardPage: React.FC = () => {
  const {
    tvl,
    pnl,
    realized_pnl,
    unrealized_pnl,
    activeGroupsCount,
    free_usdt,
    fetchEngineData,
    total_trades,
    total_winning_trades,
    total_losing_trades,
    win_rate
  } = useEngineStore();

  useEffect(() => {
    fetchEngineData();
    startEngineDataPolling();
    return () => stopEngineDataPolling();
  }, [fetchEngineData]);

  if (useEngineStore.getState().loading && !tvl) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <Typography>Loading Dashboard...</Typography>
      </Box>
    );
  }
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
          <FreeUsdtCard freeUsdt={free_usdt} />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 4 }}>
          <PnlCard pnl={pnl} realizedPnl={realized_pnl} unrealizedPnl={unrealized_pnl} />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 4 }}>
          <ActiveGroupsWidget count={activeGroupsCount} />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 4 }}>
          <WinLossWidget
            totalTrades={total_trades}
            wins={total_winning_trades}
            losses={total_losing_trades}
            winRate={win_rate}
          />
        </Grid>
        <Grid size={{ xs: 12 }}>
          <EquityCurveChart />
        </Grid>
      </Grid>
    </Box>
  );
};

export default DashboardPage;
