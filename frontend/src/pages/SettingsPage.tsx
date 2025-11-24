import React, { useEffect, useState } from 'react';
import { Box, Typography, Tabs, Tab, CircularProgress, Alert, Paper, Button, TextField, Grid, Checkbox, FormControlLabel } from '@mui/material';
import { useForm, useFieldArray, Controller, Resolver, FieldError } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import useConfigStore from '../store/configStore';

// Define Zod schemas for validation
const exchangeSettingsSchema = z.object({
  exchange: z.string().min(1, 'Exchange is required'),
  api_key: z.string().optional(),
  secret_key: z.string().optional(),
});

const riskEngineConfigSchema = z.object({
  max_open_positions_global: z.number().min(0),
  max_open_positions_per_symbol: z.number().min(0),
  max_total_exposure_usd: z.number().min(0),
  max_daily_loss_usd: z.number().min(0),
  loss_threshold_percent: z.number().max(0),
  timer_start_condition: z.string().min(1),
  post_full_wait_minutes: z.number().min(0),
  max_winners_to_combine: z.number().min(0),
  use_trade_age_filter: z.boolean(),
  age_threshold_minutes: z.number().min(0),
  require_full_pyramids: z.boolean(),
  reset_timer_on_replacement: z.boolean(),
  partial_close_enabled: z.boolean(),
  min_close_notional: z.number().min(0),
});

const dcaLevelConfigSchema = z.object({
  gap_percent: z.number(),
  weight_percent: z.number(),
  tp_percent: z.number(),
});

const dcaGridConfigSchema = z.array(dcaLevelConfigSchema);

const appSettingsSchema = z.object({
  username: z.string().min(1, 'Username is required'),
  email: z.string().email('Invalid email address'),
  webhook_secret: z.string().optional(),
});

const formSchema = z.object({
  exchangeSettings: exchangeSettingsSchema,
  riskEngineConfig: riskEngineConfigSchema,
  dcaGridConfig: dcaGridConfigSchema,
  appSettings: appSettingsSchema,
});

type FormValues = {
  exchangeSettings: z.infer<typeof exchangeSettingsSchema>;
  riskEngineConfig: z.infer<typeof riskEngineConfigSchema>;
  dcaGridConfig: z.infer<typeof dcaGridConfigSchema>;
  appSettings: z.infer<typeof appSettingsSchema>;
};

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function CustomTabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;

  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`simple-tabpanel-${index}`}
      aria-labelledby={`simple-tab-${index}`}
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

function a11yProps(index: number) {
  return {
    id: `simple-tab-${index}`,
    'aria-controls': `simple-tabpanel-${index}`,
  };
}

const SettingsPage: React.FC = () => {
  const { settings, supportedExchanges, loading, error, fetchSettings, updateSettings, fetchSupportedExchanges } = useConfigStore();
  const [currentTab, setCurrentTab] = useState(0);

  useEffect(() => {
    fetchSettings();
    fetchSupportedExchanges();
  }, [fetchSettings, fetchSupportedExchanges]);

  const { handleSubmit, control, reset, watch, formState: { errors } } = useForm<FormValues>({
    resolver: zodResolver(formSchema) as Resolver<FormValues>,
    defaultValues: {
      exchangeSettings: {
        exchange: settings?.exchange || '',
        api_key: '',
        secret_key: '',
      },
      // ... (keep other defaults)
      riskEngineConfig: settings?.risk_config || {
        max_open_positions_global: 10,
        max_open_positions_per_symbol: 1,
        max_total_exposure_usd: 10000,
        max_daily_loss_usd: 500,
        loss_threshold_percent: -1.5,
        timer_start_condition: "after_all_dca_filled",
        post_full_wait_minutes: 15,
        max_winners_to_combine: 3,
        use_trade_age_filter: false,
        age_threshold_minutes: 120,
        require_full_pyramids: true,
        reset_timer_on_replacement: false,
        partial_close_enabled: true,
        min_close_notional: 10,
      },
      dcaGridConfig: settings?.dca_grid_config || [],
      appSettings: {
        username: settings?.username || '',
        email: settings?.email || '',
        webhook_secret: settings?.webhook_secret || '',
      },
    },
  });

  // Watch the selected exchange to show status
  const selectedExchange = watch("exchangeSettings.exchange");

  // ... (keep useEffects)

  useEffect(() => {
    if (settings) {
      reset({
        exchangeSettings: {
          exchange: settings.exchange,
          api_key: '', // Always reset these to empty for security
          secret_key: '',
        },
        riskEngineConfig: settings.risk_config,
        dcaGridConfig: settings.dca_grid_config,
        appSettings: {
          username: settings.username,
          email: settings.email,
          webhook_secret: settings.webhook_secret,
        },
      });
    }
  }, [settings, reset]);

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setCurrentTab(newValue);
  };

  const { fields: dcaFields, append: appendDca, remove: removeDca } = useFieldArray({
    control,
    name: "dcaGridConfig"
  });

  const onSubmit = async (data: FormValues) => {
    // Transform data to match backend UserUpdate schema
    const payload: any = {
      exchange: data.exchangeSettings.exchange,
      risk_config: data.riskEngineConfig,
      dca_grid_config: data.dcaGridConfig,
      username: data.appSettings.username,
      email: data.appSettings.email,
      webhook_secret: data.appSettings.webhook_secret,
    };

    // Only send keys if they are provided
    if (data.exchangeSettings.api_key && data.exchangeSettings.secret_key) {
        payload.api_key = data.exchangeSettings.api_key;
        payload.secret_key = data.exchangeSettings.secret_key;
    }

    await updateSettings(payload);
    // Clear the key fields after save for security
    reset({ ...data, exchangeSettings: { ...data.exchangeSettings, api_key: '', secret_key: '' } });
  };

  // Helper to check if keys exist for the selected exchange
  const hasKeysForExchange = (exchange: string) => {
    if (!settings?.encrypted_api_keys) return false;
    // Check if it's the new dict structure or legacy
    const keys = settings.encrypted_api_keys as any;
    return !!keys[exchange];
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 5 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="error">Error loading settings: {error}</Alert>
      </Box>
    );
  }

  // ... (keep render logic up to form)

  return (
    <Box sx={{ flexGrow: 1, p: 3 }}>
        {/* ... (keep header) */}
        <Typography variant="h4" gutterBottom>
        Settings
      </Typography>
      <Paper sx={{ p: 3 }}>
        <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
            {/* ... (keep tabs) */}
          <Tabs value={currentTab} onChange={handleTabChange} aria-label="settings tabs">
            <Tab label="Exchange" {...a11yProps(0)} />
            <Tab label="Risk Engine" {...a11yProps(1)} />
            <Tab label="DCA Grid" {...a11yProps(2)} />
            <Tab label="Account" {...a11yProps(3)} />
          </Tabs>
        </Box>

        <form onSubmit={handleSubmit(onSubmit)}>
          <CustomTabPanel value={currentTab} index={0}>
            {/* Exchange Settings */}
            <Typography variant="h6" gutterBottom>Exchange Configuration</Typography>
            
            <Controller
              name="exchangeSettings.exchange"
              control={control}
              render={({ field }) => (
                <TextField
                  {...field}
                  select
                  label="Active Exchange"
                  fullWidth
                  margin="normal"
                  error={!!errors.exchangeSettings?.exchange}
                  helperText={errors.exchangeSettings?.exchange?.message || "Select the exchange to trade on AND configure keys for."}
                  SelectProps={{ native: true }}
                >
                  {supportedExchanges.map((exchange) => (
                    <option key={exchange} value={exchange}>
                      {exchange}
                    </option>
                  ))}
                </TextField>
              )}
            />

            <Box sx={{ mt: 2, mb: 2 }}>
                {selectedExchange && (
                    <Alert severity={hasKeysForExchange(selectedExchange) ? "success" : "warning"}>
                        {hasKeysForExchange(selectedExchange) 
                            ? `API Keys are currently configured for ${selectedExchange}.` 
                            : `No API Keys found for ${selectedExchange}. Please enter them below.`}
                    </Alert>
                )}
            </Box>

            <Typography variant="subtitle1" sx={{ mt: 2 }}>Update API Keys (Optional)</Typography>
            <Typography variant="caption" color="textSecondary">
                Leave blank to keep existing keys. Enter new keys to overwrite.
            </Typography>

            <Controller
              name="exchangeSettings.api_key"
              control={control}
              render={({ field }) => (
                <TextField
                  {...field}
                  label="New API Key (Public)"
                  fullWidth
                  margin="normal"
                  error={!!errors.exchangeSettings?.api_key}
                  helperText={errors.exchangeSettings?.api_key?.message}
                />
              )}
            />
            <Controller
              name="exchangeSettings.secret_key"
              control={control}
              render={({ field }) => (
                <TextField
                  {...field}
                  label="New API Key (Private)"
                  fullWidth
                  margin="normal"
                  type="password"
                  error={!!errors.exchangeSettings?.secret_key}
                  helperText={errors.exchangeSettings?.secret_key?.message}
                />
              )}
            />
          </CustomTabPanel>
          {/* ... (keep other panels) */}
          <CustomTabPanel value={currentTab} index={1}>
            {/* Risk Engine Settings */}
            <Typography variant="h6" gutterBottom>Risk Engine Configuration</Typography>
            <Grid container spacing={2}>
              {Object.keys(riskEngineConfigSchema.shape).map((key) => {
                const fieldError = errors.riskEngineConfig?.[key as keyof typeof errors.riskEngineConfig] as FieldError | undefined;
                return (
                  <Grid size={{ xs: 12, sm: 6 }} key={key}>
                    <Controller
                      name={`riskEngineConfig.${key}` as keyof FormValues}
                      control={control}
                      render={({ field }) => {
                        const isBoolean = typeof field.value === 'boolean';
                        const isString = typeof field.value === 'string';

                        if (isBoolean) {
                          return (
                            <FormControlLabel
                              control={
                                <Checkbox
                                  checked={field.value as unknown as boolean}
                                  onChange={(e) => field.onChange(e.target.checked)}
                                />
                              }
                              label={key.replace(/([A-Z])/g, ' $1').replace(/_([a-z])/g, ' $1').replace(/^./, str => str.toUpperCase())}
                            />
                          );
                        }

                        return (
                          <TextField
                            {...field}
                            label={key.replace(/([A-Z])/g, ' $1').replace(/_([a-z])/g, ' $1').replace(/^./, str => str.toUpperCase())} // Basic label formatting
                            fullWidth
                            margin="normal"
                            type={isString ? 'text' : 'number'}
                            inputProps={{ step: 'any' }}
                            onChange={(e) => field.onChange(e.target.value)}
                            error={!!fieldError}
                            helperText={fieldError?.message}
                          />
                        );
                      }}
                    />
                  </Grid>
                );
              })}
            </Grid>
          </CustomTabPanel>

          <CustomTabPanel value={currentTab} index={2}>
            {/* DCA Grid Settings */}
            <Typography variant="h6" gutterBottom>DCA Grid Configuration</Typography>
            {dcaFields.map((field, index) => (
              <Paper elevation={1} sx={{ p: 2, mb: 2 }} key={field.id}>
                <Grid container spacing={2} alignItems="center">
                  <Grid size={{ xs: 12, sm: 3 }}>
                    <Controller
                      name={`dcaGridConfig.${index}.gap_percent`}
                      control={control}
                      render={({ field }) => (
                        <TextField
                          {...field}
                          label="Gap %"
                          fullWidth
                          margin="normal"
                          type="number"
                          inputProps={{ step: 'any' }}
                          error={!!errors.dcaGridConfig?.[index]?.gap_percent}
                          helperText={errors.dcaGridConfig?.[index]?.gap_percent?.message}
                        />
                      )}
                    />
                  </Grid>
                  <Grid size={{ xs: 12, sm: 3 }}>
                    <Controller
                      name={`dcaGridConfig.${index}.weight_percent`}
                      control={control}
                      render={({ field }) => (
                        <TextField
                          {...field}
                          label="Weight %"
                          fullWidth
                          margin="normal"
                          type="number"
                          inputProps={{ step: 'any' }}
                          error={!!errors.dcaGridConfig?.[index]?.weight_percent}
                          helperText={errors.dcaGridConfig?.[index]?.weight_percent?.message}
                        />
                      )}
                    />
                  </Grid>
                  <Grid size={{ xs: 12, sm: 3 }}>
                    <Controller
                      name={`dcaGridConfig.${index}.tp_percent`}
                      control={control}
                      render={({ field }) => (
                        <TextField
                          {...field}
                          label="TP %"
                          fullWidth
                          margin="normal"
                          type="number"
                          inputProps={{ step: 'any' }}
                          error={!!errors.dcaGridConfig?.[index]?.tp_percent}
                          helperText={errors.dcaGridConfig?.[index]?.tp_percent?.message}
                        />
                      )}
                    />
                  </Grid>
                  <Grid size={{ xs: 12, sm: 3 }}>
                    <Button color="error" onClick={() => removeDca(index)}>Remove</Button>
                  </Grid>
                </Grid>
              </Paper>
            ))}
            <Button variant="outlined" onClick={() => appendDca({ gap_percent: 0, weight_percent: 0, tp_percent: 0 })} sx={{ mt: 2 }}>
              Add DCA Level
            </Button>
            {errors.dcaGridConfig && <Alert severity="error" sx={{ mt: 2 }}>{errors.dcaGridConfig.message}</Alert>}
          </CustomTabPanel>

          <CustomTabPanel value={currentTab} index={3}>
            {/* App Settings (User Account) */}
            <Typography variant="h6" gutterBottom>Account Settings</Typography>
            <Controller
              name="appSettings.username"
              control={control}
              render={({ field }) => (
                <TextField
                  {...field}
                  label="Username"
                  fullWidth
                  margin="normal"
                  error={!!errors.appSettings?.username}
                  helperText={errors.appSettings?.username?.message}
                />
              )}
            />
            <Controller
              name="appSettings.email"
              control={control}
              render={({ field }) => (
                <TextField
                  {...field}
                  label="Email"
                  fullWidth
                  margin="normal"
                  type="email"
                  error={!!errors.appSettings?.email}
                  helperText={errors.appSettings?.email?.message}
                />
              )}
            />
            <Controller
              name="appSettings.webhook_secret"
              control={control}
              render={({ field }) => (
                <TextField
                  {...field}
                  label="Webhook Secret"
                  fullWidth
                  margin="normal"
                  error={!!errors.appSettings?.webhook_secret}
                  helperText={errors.appSettings?.webhook_secret?.message}
                  disabled // Webhook secret is typically read-only or generated, not freely edited
                />
              )}
            />
          </CustomTabPanel>
          
          <Button type="submit" variant="contained" color="success" sx={{ mt: 3 }}>
            Save Settings
          </Button>
        </form>
      </Paper>
    </Box>
  );
};

export default SettingsPage;