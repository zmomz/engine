import React from 'react';
import { Box, Tab, Tabs, Typography } from '@mui/material';

import ExchangeApiSettings from '../components/ExchangeApiSettings';
import RiskEngineSettings from '../components/RiskEngineSettings';
import ExecutionPoolSettings from '../components/ExecutionPoolSettings';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;

  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`settings-tabpanel-${index}`}
      aria-labelledby={`settings-tab-${index}`}
      {...other}
    >
      {value === index && (
        <Box sx={{ p: 3 }}>
          {children}
        </Box>
      )}
    </div>
  );
}

const SettingsPage: React.FC = () => {
  const [value, setValue] = React.useState(0);

  const handleChange = (event: React.SyntheticEvent, newValue: number) => {
    setValue(newValue);
  };

  return (
    <Box sx={{ width: '100%' }}>
      <Typography variant="h4" gutterBottom>
        Settings
      </Typography>
      <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
        <Tabs value={value} onChange={handleChange} aria-label="settings tabs">
          <Tab label="Exchange API" id="settings-tab-0" />
          <Tab label="Risk Engine" id="settings-tab-1" />
          <Tab label="Execution Pool" id="settings-tab-2" />
        </Tabs>
      </Box>
      <TabPanel value={value} index={0}>
        <ExchangeApiSettings />
      </TabPanel>
      <TabPanel value={value} index={1}>
        <RiskEngineSettings />
      </TabPanel>
      <TabPanel value={value} index={2}>
        <ExecutionPoolSettings />
      </TabPanel>
    </Box>
  );
};

export default SettingsPage;