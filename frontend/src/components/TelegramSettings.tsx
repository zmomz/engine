// File: src/components/TelegramSettings.tsx

import React from 'react';
import {
  Box,
  Button,
  TextField,
  Typography,
  CircularProgress,
  Alert,
  Paper,
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
      <Typography variant="h5" gutterBottom>
        Telegram Signal Broadcasting
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        Configure automatic signal broadcasting to your Telegram channel
      </Typography>

      {/* REMOVE the <form> tag - we're inside parent's form */}
      <Paper sx={{ p: 3 }}>
        <Grid container spacing={3}>
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
            <Typography variant="subtitle2" gutterBottom>
              Signal Options
            </Typography>
            <Controller
              name="telegramSettings.send_entry_signals" // Update name
              control={control}
              render={({ field }) => (
                <FormControlLabel
                  control={<Switch {...field} checked={field.value} disabled={!enabled} />}
                  label="Send Entry Signals"
                />
              )}
            />
            <Controller
              name="telegramSettings.send_exit_signals" // Update name
              control={control}
              render={({ field }) => (
                <FormControlLabel
                  control={<Switch {...field} checked={field.value} disabled={!enabled} />}
                  label="Send Exit Signals"
                />
              )}
            />
            <Controller
              name="telegramSettings.update_on_pyramid" // Update name
              control={control}
              render={({ field }) => (
                <FormControlLabel
                  control={<Switch {...field} checked={field.value} disabled={!enabled} />}
                  label="Update Message on New Pyramid"
                />
              )}
            />
            <Controller
              name="telegramSettings.test_mode" // Update name
              control={control}
              render={({ field }) => (
                <FormControlLabel
                  control={<Switch {...field} checked={field.value} disabled={!enabled} />}
                  label="Test Mode (Log Only, Don't Send)"
                />
              )}
            />
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

          {/* Action Buttons - REMOVE Save button, keep test buttons */}
          <Grid size={{ xs: 12 }}>
            <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
              {/* REMOVED SAVE BUTTON */}

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
        </Grid>
      </Paper>

      {/* Keep help section as is */}
      <Paper sx={{ p: 3, mt: 3, bgcolor: 'background.default' }}>
        <Typography variant="h6" gutterBottom>
          Setup Instructions
        </Typography>
        <Typography variant="body2" component="div">
          <ol>
            <li>Create a Telegram bot by messaging @BotFather</li>
            <li>Use the command /newbot and follow the instructions</li>
            <li>Copy the bot token provided by BotFather</li>
            <li>Create a public channel and make your bot an administrator</li>
            <li>Get your channel ID (username like @channelname or numeric ID)</li>
            <li>Paste the bot token and channel ID above</li>
            <li>Click "Test Connection" to verify</li>
            <li>Click "Send Test Message" to test broadcasting</li>
            <li>Enable broadcasting and save using main "Save Settings" button</li>
          </ol>
        </Typography>
      </Paper>
    </Box>
  );
};

export default TelegramSettings;