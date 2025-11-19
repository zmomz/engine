import React from 'react';
import { Typography } from '@mui/material';
import PoolUsageWidget from './PoolUsageWidget';
import SystemStatusWidget from './SystemStatusWidget';
import PnlCard from './PnlCard';
import EquityCurveChart from './EquityCurveChart';

const DashboardPage: React.FC = () => {
  return (
    <div>
      <Typography variant="h4" gutterBottom>
        Dashboard - Global Overview
      </Typography>
      <div>
        <PoolUsageWidget />
        <SystemStatusWidget />
        <PnlCard />
        <EquityCurveChart />
      </div>
    </div>
  );
};

export default DashboardPage;
