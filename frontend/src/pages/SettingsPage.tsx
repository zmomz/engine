import React, { useEffect, useState } from 'react';
import { Box, Typography, Tabs, Tab, CircularProgress, Alert, Paper, Button, TextField, Grid, Checkbox, FormControlLabel } from '@mui/material';
import { useForm, useFieldArray, Controller, Resolver, FieldError } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import useConfigStore, { UserSettings } from '../store/configStore';

// Define Zod schemas for validation
const apiKeysSchema = z.object({
  public: z.string().min(1, 'Public key is required'),
  private: z.string().min(1, 'Private key is required'),
}).nullable().optional();

const exchangeSettingsSchema = z.object({
  exchange: z.string().min(1, 'Exchange is required'),
  encrypted_api_keys: apiKeysSchema,
});

const dcaLevelSchema = z.object({
  gap_percent: z.coerce.number().min(-100).max(100).finite('Must be a number'),
  weight_percent: z.coerce.number().min(0.1).max(100).finite('Must be a number'),
  tp_percent: z.coerce.number().min(0.1).max(100).finite('Must be a number'),
});

const dcaGridConfigSchema = z.array(dcaLevelSchema).superRefine((val, ctx) => {
  const totalWeight = val.reduce((sum, level) => sum + level.weight_percent, 0);
  if (totalWeight !== 100) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: `Total weight percentage must sum to 100, but got ${totalWeight}`,
      path: ['weight_percent'], // This path might need adjustment based on how react-hook-form handles array errors
    });
  }
});

const riskEngineConfigSchema = z.object({
  max_open_positions_global: z.coerce.number().int().min(1, 'Must be at least 1').finite('Must be a number'),
  max_open_positions_per_symbol: z.coerce.number().int().min(1, 'Must be at least 1').finite('Must be a number'),
  max_total_exposure_usd: z.coerce.number().min(0, 'Cannot be negative').finite('Must be a number'),
  max_daily_loss_usd: z.coerce.number().min(0, 'Cannot be negative').finite('Must be a number'),
  loss_threshold_percent: z.coerce.number().min(-100).max(0).finite('Must be a number'),
  timer_start_condition: z.string(),
  post_full_wait_minutes: z.coerce.number().int().min(0).finite('Must be a number'),
  max_winners_to_combine: z.coerce.number().int().min(1).finite('Must be a number'),
  use_trade_age_filter: z.boolean(),
  age_threshold_minutes: z.coerce.number().int().min(0).finite('Must be a number'),
  require_full_pyramids: z.boolean(),
  reset_timer_on_replacement: z.boolean(),
  partial_close_enabled: z.boolean(),
  min_close_notional: z.coerce.number().min(0).finite('Must be a number'),
});

const appSettingsSchema = z.object({
  username: z.string().min(1, 'Username is required'),
  email: z.string().email('Invalid email address'),
  webhook_secret: z.string().min(1, 'Webhook secret is required'),
});

// Combined form schema
const formSchema = z.object({
  exchangeSettings: exchangeSettingsSchema,
  riskEngineConfig: riskEngineConfigSchema,
  dcaGridConfig: dcaGridConfigSchema,
  appSettings: appSettingsSchema,
});

type FormValues = z.infer<typeof formSchema>;

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

  const { handleSubmit, control, reset, formState: { errors } } = useForm<FormValues>({
    resolver: zodResolver(formSchema) as Resolver<FormValues>,
    defaultValues: {
      exchangeSettings: {
        exchange: settings?.exchange || '',
        encrypted_api_keys: settings?.encrypted_api_keys || null,
      },
      riskEngineConfig: settings?.risk_config || { // Default to an empty object or a full default structure
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
      dcaGridConfig: settings?.dca_grid_config || [], // Default to an empty array
      appSettings: {
        username: settings?.username || '',
        email: settings?.email || '',
        webhook_secret: settings?.webhook_secret || '',
      },
    },
  });

  const { fields: dcaFields, append: appendDca, remove: removeDca } = useFieldArray({
    control,
    name: "dcaGridConfig",
  });

  useEffect(() => {
    fetchSettings();
    fetchSupportedExchanges();
  }, [fetchSettings, fetchSupportedExchanges]);

  useEffect(() => {
    if (settings) {
      reset({
        exchangeSettings: {
          exchange: settings.exchange,
          encrypted_api_keys: settings.encrypted_api_keys,
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

  const onSubmit = async (data: FormValues) => {
    // Transform data to match backend UserUpdate schema
    const payload: Partial<UserSettings> = {
      exchange: data.exchangeSettings.exchange,
      encrypted_api_keys: data.exchangeSettings.encrypted_api_keys,
      risk_config: data.riskEngineConfig,
      dca_grid_config: data.dcaGridConfig,
      username: data.appSettings.username,
      email: data.appSettings.email,
      webhook_secret: data.appSettings.webhook_secret,
    };
    await updateSettings(payload);
  };

  if (loading && !settings) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
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

  if (!settings) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="info">No settings found or user not authenticated.</Alert>
      </Box>
    );
  }

  return (
    <Box sx={{ flexGrow: 1, p: 3 }}>
      <Typography variant="h4" gutterBottom>
        Settings
      </Typography>
      <Paper sx={{ p: 3 }}>
        <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
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
                  label="Exchange"
                  fullWidth
                  margin="normal"
                  error={!!errors.exchangeSettings?.exchange}
                  helperText={errors.exchangeSettings?.exchange?.message}
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
            <Controller
              name="exchangeSettings.encrypted_api_keys.public"
              control={control}
              render={({ field }) => (
                <TextField
                  {...field}
                  label="API Key (Public)"
                  fullWidth
                  margin="normal"
                  error={!!errors.exchangeSettings?.encrypted_api_keys?.public}
                  helperText={errors.exchangeSettings?.encrypted_api_keys?.public?.message}
                />
              )}
            />
            <Controller
              name="exchangeSettings.encrypted_api_keys.private"
              control={control}
              render={({ field }) => (
                <TextField
                  {...field}
                  label="API Key (Private)"
                  fullWidth
                  margin="normal"
                  type="password"
                  error={!!errors.exchangeSettings?.encrypted_api_keys?.private}
                  helperText={errors.exchangeSettings?.encrypted_api_keys?.private?.message}
                />
              )}
            />
          </CustomTabPanel>

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