import React, { useEffect, useState } from 'react';
import { Box, Tab, Tabs, Typography } from '@mui/material';
import { useForm, FormProvider } from 'react-hook-form';

import ExchangeApiSettings from '../components/ExchangeApiSettings';
import RiskEngineSettings from '../components/RiskEngineSettings';
import ExecutionPoolSettings from '../components/ExecutionPoolSettings';
import api from '../services/api';
import useAuthStore from '../store/authStore';

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
  const [value, setValue] = useState(0);
  const { user } = useAuthStore();
  const methods = useForm();

  useEffect(() => {
    const fetchSettings = async () => {
      if (user) {
        try {
          const response = await api.get('/v1/settings');
          methods.reset(response.data);
        } catch (error) {
          console.error('Failed to fetch settings:', error);
        }
      }
    };
    fetchSettings();
  }, [user, methods]);

  const handleChange = (event: React.SyntheticEvent, newValue: number) => {
    setValue(newValue);
  };

  const onSubmit = async (data: any) => {
    try {
      await api.put('/v1/settings', data);
      // Optionally, show a success message
    } catch (error) {
      console.error('Failed to update settings:', error);
      // Optionally, show an error message
    }
  };

  return (
    <FormProvider {...methods}>
      <Box
        component="form"
        onSubmit={methods.handleSubmit(onSubmit)}
        sx={{ width: '100%' }}
      >
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
        <Box sx={{ p: 3 }}>
          <button type="submit">Save Settings</button>
        </Box>
      </Box>
    </FormProvider>
  );
};

export default SettingsPage;
