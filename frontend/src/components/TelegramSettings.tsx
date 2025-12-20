// File: src/components/TelegramSettings.tsx

import React from 'react';
import {
  Box,
  Button,
  TextField,
  Typography,
  CircularProgress,
  Alert,
  FormControlLabel,
  Switch,
  Grid,
} from '@mui/material';
import { Controller } from 'react-hook-form';
import useNotificationStore from '../store/notificationStore';
import api from '../services/api';

// ADD Props interface
interface TelegramSettingsProps {
  control: any; // From react-hook-form
  watch: any;   // From react-hook-form
  getValues: any; // From react-hook-form
}

// Update component to accept props
const TelegramSettings: React.FC<TelegramSettingsProps> = ({ control, watch, getValues }) => {
  const [testingConnection, setTestingConnection] = React.useState(false);
  const [sendingTest, setSendingTest] = React.useState(false);
  const [connectionStatus, setConnectionStatus] = React.useState<'success' | 'error' | null>(null);
  const showNotification = useNotificationStore((state) => state.showNotification);

  // Remove ALL useForm hooks - we'll get control from parent
  const enabled = watch('telegramSettings.enabled'); // Watch the enabled field

  // Remove the fetch useEffect - parent will handle loading data

  // Keep test functions but modify them
  const handleTestConnection = async () => {
    setTestingConnection(true);
    setConnectionStatus(null);
    const data = getValues('telegramSettings'); // Get from parent form
    try {
      await api.post('/telegram/test-connection', data);
      setConnectionStatus('success');
      showNotification('Successfully connected to Telegram bot', 'success');
    } catch (error: any) {
      console.error('Connection test failed:', error);
      setConnectionStatus('error');
      showNotification(
        error.response?.data?.detail || 'Failed to connect to Telegram bot',
        'error'
      );
    } finally {
      setTestingConnection(false);
    }
  };

  const handleSendTestMessage = async () => {
    setSendingTest(true);
    const data = getValues('telegramSettings'); // Get from parent form
    try {
      await api.post('/telegram/test-message', data); // Send current data
      showNotification('Test message sent successfully', 'success');
    } catch (error: any) {
      console.error('Failed to send test message:', error);
      showNotification(
        error.response?.data?.detail || 'Failed to send test message',
        'error'
      );
    } finally {
      setSendingTest(false);
    }
  };

  return (
    <Box>
      <Grid container spacing={{ xs: 1.5, sm: 2 }}>
          {/* Enable/Disable */}
          <Grid size={{ xs: 12 }}>
            <Controller
              name="telegramSettings.enabled" // Update name with prefix
              control={control}
              render={({ field }) => (
                <FormControlLabel
                  control={<Switch {...field} checked={field.value} />}
                  label="Enable Telegram Broadcasting"
                />
              )}
            />
          </Grid>

          {/* Bot Token */}
          <Grid size={{ xs: 12, md: 6 }}>
            <Controller
              name="telegramSettings.bot_token" // Update name
              control={control}
              render={({ field }) => (
                <TextField
                  {...field}
                  fullWidth
                  label="Bot Token"
                  placeholder="123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
                  type="password"
                  error={false} // Parent handles validation
                  helperText="Get from @BotFather on Telegram"
                  disabled={!enabled}
                />
              )}
            />
          </Grid>

          {/* Channel ID */}
          <Grid size={{ xs: 12, md: 6 }}>
            <Controller
              name="telegramSettings.channel_id" // Update name
              control={control}
              render={({ field }) => (
                <TextField
                  {...field}
                  fullWidth
                  label="Channel ID"
                  placeholder="@algomakers_signals or -100123456789"
                  helperText="Channel username or numeric ID"
                  disabled={!enabled}
                />
              )}
            />
          </Grid>

          {/* Channel Name */}
          <Grid size={{ xs: 12 }}>
            <Controller
              name="telegramSettings.channel_name" // Update name
              control={control}
              render={({ field }) => (
                <TextField
                  {...field}
                  fullWidth
                  label="Channel Name"
                  disabled={!enabled}
                />
              )}
            />
          </Grid>

          {/* Engine Signature */}
          <Grid size={{ xs: 12 }}>
            <Controller
              name="telegramSettings.engine_signature" // Update name
              control={control}
              render={({ field }) => (
                <TextField
                  {...field}
                  fullWidth
                  multiline
                  rows={3}
                  label="Engine Signature"
                  helperText="Shown in signal messages"
                  disabled={!enabled}
                />
              )}
            />
          </Grid>

          {/* Signal Options */}
          <Grid size={{ xs: 12 }}>
            <Typography variant="subtitle2" gutterBottom sx={{ fontSize: { xs: '0.8rem', sm: '0.875rem' } }}>
              Signal Options
            </Typography>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
              <Controller
                name="telegramSettings.send_entry_signals"
                control={control}
                render={({ field }) => (
                  <FormControlLabel
                    control={<Switch {...field} checked={field.value} disabled={!enabled} size="small" />}
                    label={<Box component="span" sx={{ fontSize: { xs: '0.8rem', sm: '0.875rem' } }}>Send Entry Signals</Box>}
                    sx={{ ml: 0 }}
                  />
                )}
              />
              <Controller
                name="telegramSettings.send_exit_signals"
                control={control}
                render={({ field }) => (
                  <FormControlLabel
                    control={<Switch {...field} checked={field.value} disabled={!enabled} size="small" />}
                    label={<Box component="span" sx={{ fontSize: { xs: '0.8rem', sm: '0.875rem' } }}>Send Exit Signals</Box>}
                    sx={{ ml: 0 }}
                  />
                )}
              />
              <Controller
                name="telegramSettings.update_on_pyramid"
                control={control}
                render={({ field }) => (
                  <FormControlLabel
                    control={<Switch {...field} checked={field.value} disabled={!enabled} size="small" />}
                    label={<Box component="span" sx={{ fontSize: { xs: '0.8rem', sm: '0.875rem' } }}>Update on Pyramid</Box>}
                    sx={{ ml: 0 }}
                  />
                )}
              />
              <Controller
                name="telegramSettings.test_mode"
                control={control}
                render={({ field }) => (
                  <FormControlLabel
                    control={<Switch {...field} checked={field.value} disabled={!enabled} size="small" />}
                    label={<Box component="span" sx={{ fontSize: { xs: '0.8rem', sm: '0.875rem' } }}>Test Mode (Log Only)</Box>}
                    sx={{ ml: 0 }}
                  />
                )}
              />
            </Box>
          </Grid>

          {/* Connection Status */}
          {connectionStatus && (
            <Grid size={{ xs: 12 }}>
              <Alert severity={connectionStatus}>
                {connectionStatus === 'success'
                  ? 'Bot connection successful!'
                  : 'Failed to connect to bot. Check your token.'}
              </Alert>
            </Grid>
          )}

          {/* Action Buttons */}
          <Grid size={{ xs: 12 }}>
            <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
              <Button
                type="button"
                variant="outlined"
                onClick={handleTestConnection}
                disabled={!enabled || testingConnection}
                startIcon={testingConnection && <CircularProgress size={20} />}
              >
                {testingConnection ? 'Testing...' : 'Test Connection'}
              </Button>

              <Button
                type="button"
                variant="outlined"
                onClick={handleSendTestMessage}
                disabled={!enabled || sendingTest}
                startIcon={sendingTest && <CircularProgress size={20} />}
              >
                {sendingTest ? 'Sending...' : 'Send Test Message'}
              </Button>
            </Box>
          </Grid>

          {/* Setup Instructions - hidden on mobile */}
          <Grid size={{ xs: 12 }} sx={{ display: { xs: 'none', sm: 'block' } }}>
            <Box sx={{ p: 1.5, bgcolor: 'background.default', borderRadius: 1 }}>
              <Typography variant="subtitle2" gutterBottom sx={{ fontSize: '0.8rem' }}>
                Setup Instructions
              </Typography>
              <Typography variant="body2" color="text.secondary" component="div" sx={{ fontSize: '0.75rem' }}>
                <ol style={{ margin: 0, paddingLeft: 16 }}>
                  <li>Create a bot via @BotFather</li>
                  <li>Copy the bot token</li>
                  <li>Add bot as admin to your channel</li>
                  <li>Enter token & channel ID, then test</li>
                </ol>
              </Typography>
            </Box>
          </Grid>
        </Grid>
    </Box>
  );
};

export default TelegramSettings;