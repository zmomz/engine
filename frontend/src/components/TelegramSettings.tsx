// File: src/components/TelegramSettings.tsx

import React, { useState } from 'react';
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
  Divider,
  Collapse,
  IconButton,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import { Controller } from 'react-hook-form';
import useNotificationStore from '../store/notificationStore';
import api from '../services/api';

interface TelegramSettingsProps {
  control: any;
  watch: any;
  getValues: any;
}

const TelegramSettings: React.FC<TelegramSettingsProps> = ({ control, watch, getValues }) => {
  const [testingConnection, setTestingConnection] = useState(false);
  const [sendingTest, setSendingTest] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<'success' | 'error' | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const showNotification = useNotificationStore((state) => state.showNotification);

  const enabled = watch('telegramSettings.enabled');
  const quietHoursEnabled = watch('telegramSettings.quiet_hours_enabled');

  const handleTestConnection = async () => {
    setTestingConnection(true);
    setConnectionStatus(null);
    const data = getValues('telegramSettings');
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
    const data = getValues('telegramSettings');
    try {
      await api.post('/telegram/test-message', data);
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

  const SwitchField = ({ name, label, disabled = false }: { name: string; label: string; disabled?: boolean }) => (
    <Controller
      name={name}
      control={control}
      render={({ field }) => (
        <FormControlLabel
          control={<Switch {...field} checked={field.value} disabled={!enabled || disabled} size="small" />}
          label={<Box component="span" sx={{ fontSize: { xs: '0.8rem', sm: '0.875rem' } }}>{label}</Box>}
          sx={{ ml: 0 }}
        />
      )}
    />
  );

  return (
    <Box>
      <Grid container spacing={{ xs: 1.5, sm: 2 }}>
        {/* Enable/Disable */}
        <Grid size={{ xs: 12 }}>
          <Controller
            name="telegramSettings.enabled"
            control={control}
            render={({ field }) => (
              <FormControlLabel
                control={<Switch {...field} checked={field.value} />}
                label="Enable Telegram Broadcasting"
              />
            )}
          />
        </Grid>

        {/* Connection Settings */}
        <Grid size={{ xs: 12 }}>
          <Typography variant="subtitle2" sx={{ fontSize: { xs: '0.8rem', sm: '0.875rem' }, mb: 1, color: 'text.secondary' }}>
            Connection
          </Typography>
        </Grid>

        <Grid size={{ xs: 12, md: 6 }}>
          <Controller
            name="telegramSettings.bot_token"
            control={control}
            render={({ field }) => (
              <TextField
                {...field}
                fullWidth
                size="small"
                label="Bot Token"
                placeholder="123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
                type="password"
                helperText="Get from @BotFather on Telegram"
                disabled={!enabled}
              />
            )}
          />
        </Grid>

        <Grid size={{ xs: 12, md: 6 }}>
          <Controller
            name="telegramSettings.channel_id"
            control={control}
            render={({ field }) => (
              <TextField
                {...field}
                fullWidth
                size="small"
                label="Channel ID"
                placeholder="@algomakers_signals or -100123456789"
                helperText="Channel username or numeric ID"
                disabled={!enabled}
              />
            )}
          />
        </Grid>

        <Grid size={{ xs: 12, md: 6 }}>
          <Controller
            name="telegramSettings.channel_name"
            control={control}
            render={({ field }) => (
              <TextField
                {...field}
                fullWidth
                size="small"
                label="Channel Name"
                disabled={!enabled}
              />
            )}
          />
        </Grid>

        <Grid size={{ xs: 12, md: 6 }}>
          <Controller
            name="telegramSettings.engine_signature"
            control={control}
            render={({ field }) => (
              <TextField
                {...field}
                fullWidth
                size="small"
                multiline
                rows={2}
                label="Engine Signature"
                helperText="Shown in signal messages"
                disabled={!enabled}
              />
            )}
          />
        </Grid>

        <Grid size={{ xs: 12 }}>
          <Divider sx={{ my: 1 }} />
        </Grid>

        {/* Message Types */}
        <Grid size={{ xs: 12 }}>
          <Typography variant="subtitle2" sx={{ fontSize: { xs: '0.8rem', sm: '0.875rem' }, mb: 1, color: 'text.secondary' }}>
            Message Types
          </Typography>
        </Grid>

        <Grid size={{ xs: 12, sm: 6, md: 4 }}>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
            <Typography variant="caption" color="text.secondary" sx={{ mb: 0.5 }}>Position Lifecycle</Typography>
            <SwitchField name="telegramSettings.send_entry_signals" label="Entry Signals" />
            <SwitchField name="telegramSettings.send_exit_signals" label="Exit Signals" />
            <SwitchField name="telegramSettings.send_status_updates" label="Status Changes" />
          </Box>
        </Grid>

        <Grid size={{ xs: 12, sm: 6, md: 4 }}>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
            <Typography variant="caption" color="text.secondary" sx={{ mb: 0.5 }}>Fill Updates</Typography>
            <SwitchField name="telegramSettings.send_dca_fill_updates" label="DCA Leg Fills" />
            <SwitchField name="telegramSettings.send_pyramid_updates" label="New Pyramids" />
            <SwitchField name="telegramSettings.send_tp_hit_updates" label="TP Hits" />
          </Box>
        </Grid>

        <Grid size={{ xs: 12, sm: 6, md: 4 }}>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
            <Typography variant="caption" color="text.secondary" sx={{ mb: 0.5 }}>Alerts (Urgent)</Typography>
            <SwitchField name="telegramSettings.send_failure_alerts" label="Failure Alerts" />
            <SwitchField name="telegramSettings.send_risk_alerts" label="Risk Alerts" />
          </Box>
        </Grid>

        <Grid size={{ xs: 12 }}>
          <Divider sx={{ my: 1 }} />
        </Grid>

        {/* Advanced Options - Collapsible */}
        <Grid size={{ xs: 12 }}>
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              cursor: 'pointer',
              userSelect: 'none',
            }}
            onClick={() => setShowAdvanced(!showAdvanced)}
          >
            <Typography variant="subtitle2" sx={{ fontSize: { xs: '0.8rem', sm: '0.875rem' }, color: 'text.secondary' }}>
              Advanced Options
            </Typography>
            <IconButton size="small" sx={{ ml: 0.5 }}>
              {showAdvanced ? <ExpandLessIcon fontSize="small" /> : <ExpandMoreIcon fontSize="small" />}
            </IconButton>
          </Box>
        </Grid>

        <Grid size={{ xs: 12 }}>
          <Collapse in={showAdvanced}>
            <Grid container spacing={{ xs: 1.5, sm: 2 }}>
              {/* Message Strategy */}
              <Grid size={{ xs: 12, sm: 6 }}>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
                  <Typography variant="caption" color="text.secondary" sx={{ mb: 0.5 }}>Message Strategy</Typography>
                  <SwitchField name="telegramSettings.update_existing_message" label="Update existing message (less spam)" />
                  <SwitchField name="telegramSettings.update_on_pyramid" label="Update on new pyramid" />
                </Box>
              </Grid>

              <Grid size={{ xs: 12, sm: 6 }}>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
                  <Typography variant="caption" color="text.secondary" sx={{ mb: 0.5 }}>Show in Messages</Typography>
                  <SwitchField name="telegramSettings.show_unrealized_pnl" label="Unrealized P&L" />
                  <SwitchField name="telegramSettings.show_invested_amount" label="Invested Amount" />
                  <SwitchField name="telegramSettings.show_duration" label="Position Duration" />
                </Box>
              </Grid>

              {/* Threshold Alerts */}
              <Grid size={{ xs: 12 }}>
                <Typography variant="caption" color="text.secondary" sx={{ mb: 0.5, display: 'block' }}>
                  Threshold Alerts (Optional)
                </Typography>
              </Grid>

              <Grid size={{ xs: 12, sm: 6 }}>
                <Controller
                  name="telegramSettings.alert_loss_threshold_percent"
                  control={control}
                  render={({ field }) => (
                    <TextField
                      {...field}
                      value={field.value ?? ''}
                      onChange={(e) => {
                        const val = e.target.value;
                        field.onChange(val === '' ? null : parseFloat(val));
                      }}
                      fullWidth
                      size="small"
                      type="number"
                      label="Alert if loss exceeds (%)"
                      placeholder="e.g., 5"
                      helperText="Leave empty to disable"
                      disabled={!enabled}
                      inputProps={{ step: "0.1" }}
                    />
                  )}
                />
              </Grid>

              <Grid size={{ xs: 12, sm: 6 }}>
                <Controller
                  name="telegramSettings.alert_profit_threshold_percent"
                  control={control}
                  render={({ field }) => (
                    <TextField
                      {...field}
                      value={field.value ?? ''}
                      onChange={(e) => {
                        const val = e.target.value;
                        field.onChange(val === '' ? null : parseFloat(val));
                      }}
                      fullWidth
                      size="small"
                      type="number"
                      label="Alert if profit exceeds (%)"
                      placeholder="e.g., 10"
                      helperText="Leave empty to disable"
                      disabled={!enabled}
                      inputProps={{ step: "0.1" }}
                    />
                  )}
                />
              </Grid>

              {/* Quiet Hours */}
              <Grid size={{ xs: 12 }}>
                <Typography variant="caption" color="text.secondary" sx={{ mb: 0.5, display: 'block' }}>
                  Quiet Hours (Optional)
                </Typography>
              </Grid>

              <Grid size={{ xs: 12 }}>
                <SwitchField name="telegramSettings.quiet_hours_enabled" label="Enable Quiet Hours" />
              </Grid>

              {quietHoursEnabled && (
                <>
                  <Grid size={{ xs: 6, sm: 3 }}>
                    <Controller
                      name="telegramSettings.quiet_hours_start"
                      control={control}
                      render={({ field }) => (
                        <TextField
                          {...field}
                          value={field.value ?? ''}
                          onChange={(e) => field.onChange(e.target.value || null)}
                          fullWidth
                          size="small"
                          label="Start Time"
                          placeholder="22:00"
                          helperText="UTC time"
                          disabled={!enabled}
                        />
                      )}
                    />
                  </Grid>

                  <Grid size={{ xs: 6, sm: 3 }}>
                    <Controller
                      name="telegramSettings.quiet_hours_end"
                      control={control}
                      render={({ field }) => (
                        <TextField
                          {...field}
                          value={field.value ?? ''}
                          onChange={(e) => field.onChange(e.target.value || null)}
                          fullWidth
                          size="small"
                          label="End Time"
                          placeholder="08:00"
                          helperText="UTC time"
                          disabled={!enabled}
                        />
                      )}
                    />
                  </Grid>

                  <Grid size={{ xs: 12, sm: 6 }}>
                    <SwitchField name="telegramSettings.quiet_hours_urgent_only" label="Send urgent alerts during quiet hours" />
                  </Grid>
                </>
              )}

              {/* Test Mode */}
              <Grid size={{ xs: 12 }}>
                <Divider sx={{ my: 1 }} />
                <Typography variant="caption" color="text.secondary" sx={{ mb: 0.5, display: 'block' }}>
                  Testing
                </Typography>
                <SwitchField name="telegramSettings.test_mode" label="Test Mode (log messages without sending)" />
              </Grid>
            </Grid>
          </Collapse>
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
          <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', mt: 1 }}>
            <Button
              type="button"
              variant="outlined"
              size="small"
              onClick={handleTestConnection}
              disabled={!enabled || testingConnection}
              startIcon={testingConnection && <CircularProgress size={16} />}
            >
              {testingConnection ? 'Testing...' : 'Test Connection'}
            </Button>

            <Button
              type="button"
              variant="outlined"
              size="small"
              onClick={handleSendTestMessage}
              disabled={!enabled || sendingTest}
              startIcon={sendingTest && <CircularProgress size={16} />}
            >
              {sendingTest ? 'Sending...' : 'Send Test Message'}
            </Button>
          </Box>
        </Grid>

        {/* Setup Instructions - hidden on mobile */}
        <Grid size={{ xs: 12 }} sx={{ display: { xs: 'none', sm: 'block' } }}>
          <Box sx={{ p: 1.5, bgcolor: 'background.default', borderRadius: 1, mt: 1 }}>
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
