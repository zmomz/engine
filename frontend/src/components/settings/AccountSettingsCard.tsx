import React from 'react';
import { TextField, Grid, Box, IconButton, Tooltip, Switch, Typography } from '@mui/material';
import { Control, Controller, FieldErrors } from 'react-hook-form';
import PersonIcon from '@mui/icons-material/Person';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import SettingsSectionCard from './SettingsSectionCard';
import useNotificationStore from '../../store/notificationStore';

interface AccountSettingsCardProps {
  control: Control<any>;
  errors?: FieldErrors<any>;
  webhookUrl: string;
}

const AccountSettingsCard: React.FC<AccountSettingsCardProps> = ({
  control,
  errors,
  webhookUrl,
}) => {
  const appErrors = (errors as any)?.appSettings;

  const handleCopyWebhook = () => {
    navigator.clipboard.writeText(webhookUrl);
    useNotificationStore.getState().showNotification('Webhook URL copied to clipboard', 'success');
  };

  return (
    <SettingsSectionCard
      title="Account Settings"
      icon={<PersonIcon />}
      description="Your profile and webhook configuration"
    >
      <Grid container spacing={{ xs: 1.5, sm: 2 }}>
        <Grid size={{ xs: 12, sm: 6 }}>
          <Controller
            name="appSettings.username"
            control={control}
            render={({ field }) => (
              <TextField
                {...field}
                label="Username"
                fullWidth
                size="small"
                error={!!appErrors?.username}
                helperText={appErrors?.username?.message}
              />
            )}
          />
        </Grid>

        <Grid size={{ xs: 12, sm: 6 }}>
          <Controller
            name="appSettings.email"
            control={control}
            render={({ field }) => (
              <TextField
                {...field}
                label="Email"
                fullWidth
                size="small"
                type="email"
                error={!!appErrors?.email}
                helperText={appErrors?.email?.message}
              />
            )}
          />
        </Grid>

        <Grid size={12}>
          <Box sx={{ position: 'relative' }}>
            <TextField
              label="Webhook URL"
              fullWidth
              size="small"
              value={webhookUrl}
              InputProps={{
                readOnly: true,
                sx: {
                  pr: 5,
                  '& input': {
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    fontSize: { xs: '0.7rem', sm: '0.875rem' },
                  }
                }
              }}
              helperText="Copy for TradingView alerts"
              sx={{ '& .MuiFormHelperText-root': { fontSize: { xs: '0.65rem', sm: '0.75rem' } } }}
            />
            <Tooltip title="Copy to clipboard">
              <IconButton
                onClick={handleCopyWebhook}
                sx={{
                  position: 'absolute',
                  right: 4,
                  top: 4,
                }}
                size="small"
              >
                <ContentCopyIcon sx={{ fontSize: { xs: 16, sm: 20 } }} />
              </IconButton>
            </Tooltip>
          </Box>
        </Grid>

        <Grid size={12}>
          <Controller
            name="appSettings.webhook_secret"
            control={control}
            render={({ field }) => (
              <TextField
                {...field}
                label="Webhook Secret"
                fullWidth
                size="small"
                disabled
                helperText="Auto-generated secret"
                sx={{ '& .MuiFormHelperText-root': { fontSize: { xs: '0.65rem', sm: '0.75rem' } } }}
              />
            )}
          />
        </Grid>

        <Grid size={12}>
          <Controller
            name="appSettings.secure_signals"
            control={control}
            render={({ field }) => (
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <Box>
                  <Typography variant="body2" fontWeight={500}>
                    Secure Signals
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {field.value
                      ? "Webhook secret is required in payload"
                      : "Webhook accepts signals without secret validation"}
                  </Typography>
                </Box>
                <Switch
                  checked={field.value ?? true}
                  onChange={(e) => field.onChange(e.target.checked)}
                  color="primary"
                />
              </Box>
            )}
          />
        </Grid>
      </Grid>
    </SettingsSectionCard>
  );
};

export default AccountSettingsCard;
