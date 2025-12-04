import React, { useEffect, useState } from 'react';
import { Box, Button, TextField, Typography, CircularProgress, Alert, FormControlLabel, IconButton, Divider, Paper, Tabs, Tab, List, ListItem, ListItemText, ListItemSecondaryAction, Grid, Checkbox } from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import EditIcon from '@mui/icons-material/Edit';
import { useForm, useFieldArray, Controller, Resolver, FieldError, FieldErrors } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import useConfigStore from '../store/configStore';
import useConfirmStore from '../store/confirmStore';
import useNotificationStore from '../store/notificationStore';

// Define Zod schemas for validation
const exchangeSettingsSchema = z.object({
  exchange: z.string().min(1, 'Exchange is required'),
  key_target_exchange: z.string().min(1, 'Target exchange is required'), 
  api_key: z.string().optional(),
  secret_key: z.string().optional(),
  testnet: z.boolean().optional(), // Added testnet
  account_type: z.string().optional(), // Added account_type
});

const riskEngineConfigSchema = z.object({
  max_open_positions_global: z.coerce.number().min(0),
  max_open_positions_per_symbol: z.coerce.number().min(0),
  max_total_exposure_usd: z.coerce.number().min(0),
  max_daily_loss_usd: z.coerce.number().min(0),
  loss_threshold_percent: z.coerce.number().max(0),
  timer_start_condition: z.string().min(1),
  post_full_wait_minutes: z.coerce.number().min(0),
  max_winners_to_combine: z.coerce.number().min(0),
  use_trade_age_filter: z.boolean(),
  age_threshold_minutes: z.coerce.number().min(0),
  require_full_pyramids: z.boolean(),
  reset_timer_on_replacement: z.boolean(),
  partial_close_enabled: z.boolean(),
  min_close_notional: z.coerce.number().min(0),
});

const dcaLevelConfigSchema = z.object({
  gap_percent: z.coerce.number(),
  weight_percent: z.coerce.number().gt(0, "Weight must be greater than 0"),
  tp_percent: z.coerce.number().gt(0, "Take Profit must be greater than 0"),
});

const dcaGridConfigSchema = z.object({
  levels: z.array(dcaLevelConfigSchema).superRefine((data, ctx) => {
    if (data.length === 0) return;
    const totalWeight = data.reduce((sum, item) => sum + item.weight_percent, 0);
    // Allow for small floating point discrepancies
    if (Math.abs(totalWeight - 100) > 0.01) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: `Total weight percent must sum to 100 (current: ${totalWeight.toFixed(2)})`,
        path: [] // Attach error to the array root
      });
    }
  }),
  tp_mode: z.enum(["per_leg", "aggregate", "hybrid"]),
  tp_aggregate_percent: z.coerce.number().min(0),
});

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
  const { settings, supportedExchanges, loading, error, fetchSettings, updateSettings, deleteKey, fetchSupportedExchanges } = useConfigStore();
  const [currentTab, setCurrentTab] = useState(0);

  useEffect(() => {
    fetchSettings();
    fetchSupportedExchanges();
  }, [fetchSettings, fetchSupportedExchanges]);

  const { handleSubmit, control, reset, setValue, watch, formState: { errors } } = useForm<FormValues>({
    resolver: zodResolver(formSchema) as Resolver<FormValues>,
    defaultValues: {
      exchangeSettings: {
        exchange: settings?.exchange || '',
        key_target_exchange: settings?.exchange || '',
        api_key: '',
        secret_key: '',
      },
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
      dcaGridConfig: settings?.dca_grid_config || { levels: [], tp_mode: "per_leg", tp_aggregate_percent: 0 },
      appSettings: {
        username: settings?.username || '',
        email: settings?.email || '',
        webhook_secret: settings?.webhook_secret || '',
      },
    },
  });

  // Watch the selected target exchange to show status
  const selectedTargetExchange = watch("exchangeSettings.key_target_exchange");

  useEffect(() => {
    if (settings) {
      const currentExchangeDetails = settings.configured_exchange_details?.[settings.exchange] || {};
      reset({
        exchangeSettings: {
          exchange: settings.exchange,
          key_target_exchange: settings.exchange, // Default to active exchange
          api_key: '', 
          secret_key: '',
          testnet: currentExchangeDetails.testnet || false, // Initialize testnet
          account_type: currentExchangeDetails.account_type || '', // Initialize account_type
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
    name: "dcaGridConfig.levels"
  });

  const onSubmit = async (data: FormValues) => {
    // Transform data to match backend UserUpdate schema
    const payload: any = {
      exchange: data.exchangeSettings.exchange, // This sets the ACTIVE exchange
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
        // Explicitly set the target exchange for these keys
        payload.key_target_exchange = data.exchangeSettings.key_target_exchange;
    }

    await updateSettings(payload);
    // Note: reset logic is handled by the useEffect on settings change which fires after update
  };

  const onError = (errors: FieldErrors<FormValues>) => {
    console.error("Form validation errors:", errors);
    if (errors.exchangeSettings) {
      setCurrentTab(0);
    } else if (errors.riskEngineConfig) {
      setCurrentTab(1);
    } else if (errors.dcaGridConfig) {
      setCurrentTab(2);
    } else if (errors.appSettings) {
      setCurrentTab(3);
    }
    // Optional: show a snackbar or alert
    // alert("Please correct the errors in the highlighted tab before saving.");
  };

  const handleDeleteKey = async (exchange: string) => {
    const confirmed = await useConfirmStore.getState().requestConfirm({
      title: 'Delete API Keys',
      message: `Are you sure you want to delete API keys for ${exchange}?`,
      confirmText: 'Delete',
      cancelText: 'Cancel'
    });
    if (confirmed) {
      await deleteKey(exchange);
    }
  };

  const handleEditKey = (exchange: string) => {
    setValue("exchangeSettings.key_target_exchange", exchange);
    const exchangeDetails = settings?.configured_exchange_details?.[exchange];
    if (exchangeDetails) {
      setValue("exchangeSettings.testnet", exchangeDetails.testnet || false);
      setValue("exchangeSettings.account_type", exchangeDetails.account_type || '');
    }
    // Focus the api key input? (Optional)
  };

  const isConfigured = (exchange: string) => settings?.configured_exchanges?.includes(exchange);

  if (loading && !settings) {
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
            <Tab label="System" {...a11yProps(4)} />
          </Tabs>
        </Box>

        <form onSubmit={handleSubmit(onSubmit, onError)}>
          <CustomTabPanel value={currentTab} index={0}>
            {/* Exchange Settings */}
            <Typography variant="h6" gutterBottom>Configured API Keys</Typography>
            <Paper variant="outlined" sx={{ mb: 3 }}>
                <List>
                    {settings?.configured_exchanges && settings.configured_exchanges.length > 0 ? (
                        settings.configured_exchanges.map((ex) => (
                            <ListItem key={ex} divider>
                                <ListItemText 
                                    primary={
                                        <Box display="flex" alignItems="center" gap={1}>
                                            {ex}
                                        </Box>
                                    } 
                                    secondary="API Keys Configured" 
                                />
                                <ListItemSecondaryAction>
                                    <IconButton edge="end" aria-label="edit" onClick={() => handleEditKey(ex)} sx={{ mr: 1 }}>
                                        <EditIcon />
                                    </IconButton>
                                    <IconButton edge="end" aria-label="delete" onClick={() => handleDeleteKey(ex)} color="error">
                                        <DeleteIcon />
                                    </IconButton>
                                </ListItemSecondaryAction>
                            </ListItem>
                        ))
                    ) : (
                        <ListItem>
                            <ListItemText primary="No exchanges configured." secondary="Add API keys below." />
                        </ListItem>
                    )}
                </List>
            </Paper>

            <Typography variant="h6" gutterBottom sx={{ mt: 2 }}>Add / Update API Keys</Typography>
            <Paper elevation={0} sx={{ p: 2, bgcolor: 'background.default' }}>
                <Grid container spacing={2} alignItems="flex-start">
                    <Grid size={{ xs: 12, md: 4 }}>
                         <Controller
                            name="exchangeSettings.key_target_exchange"
                            control={control}
                            render={({ field }) => (
                                <TextField
                                {...field}
                                select
                                label="Exchange to Configure"
                                fullWidth
                                margin="normal"
                                error={!!errors.exchangeSettings?.key_target_exchange}
                                SelectProps={{ native: true }}
                                InputLabelProps={{ shrink: true }}
                                >
                                {supportedExchanges.map((exchange) => (
                                    <option key={exchange} value={exchange}>
                                    {exchange}
                                    </option>
                                ))}
                                </TextField>
                            )}
                        />
                    </Grid>
                </Grid>
               
                <Box sx={{ mt: 1, mb: 2 }}>
                    {selectedTargetExchange && (
                        <Alert severity={isConfigured(selectedTargetExchange) ? "info" : "warning"}>
                            {isConfigured(selectedTargetExchange) 
                                ? `Keys are already configured for ${selectedTargetExchange}. Entering new keys will overwrite them.` 
                                : `No keys found for ${selectedTargetExchange}. Please configure them.`}
                        </Alert>
                    )}
                </Box>

                <Controller
                  name="exchangeSettings.api_key"
                  control={control}
                  render={({ field }) => (
                    <TextField
                      {...field}
                      label="API Key (Public)"
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
                      label="Secret Key (Private)"
                      fullWidth
                      margin="normal"
                      type="password"
                      error={!!errors.exchangeSettings?.secret_key}
                      helperText={errors.exchangeSettings?.secret_key?.message}
                    />
                  )}
                />
                <Controller
                  name="exchangeSettings.testnet"
                  control={control}
                  render={({ field }) => (
                    <FormControlLabel
                      control={
                        <Checkbox
                          checked={!!field.value}
                          onChange={(e) => field.onChange(e.target.checked)}
                        />
                      }
                      label="Use Testnet"
                    />
                  )}
                />
                 <Controller
                  name="exchangeSettings.account_type"
                  control={control}
                  render={({ field }) => (
                    <TextField
                      {...field}
                      label="Account Type (e.g., UNIFIED for Bybit)"
                      fullWidth
                      margin="normal"
                      error={!!errors.exchangeSettings?.account_type}
                      helperText={errors.exchangeSettings?.account_type?.message}
                    />
                  )}
                />
                <Button 
                    variant="contained" 
                    color="primary"
                    sx={{ mt: 2 }}
                    onClick={async (e) => {
                         // Prevent form submission
                         e.preventDefault();
                         e.stopPropagation();

                         const currentValues = watch("exchangeSettings");
                         
                         if (currentValues.api_key && currentValues.secret_key) {
                            const payload: any = {
                                key_target_exchange: currentValues.key_target_exchange,
                                api_key: currentValues.api_key,
                                secret_key: currentValues.secret_key,
                            };
                            // Add testnet and account_type if they have values
                            if (currentValues.testnet !== undefined) {
                                payload.testnet = currentValues.testnet;
                            }
                            if (currentValues.account_type) {
                                payload.account_type = currentValues.account_type;
                            }
                            await updateSettings(payload);
                            // Clear fields after successful update
                            setValue("exchangeSettings.api_key", "");
                            setValue("exchangeSettings.secret_key", "");
                            // Optionally clear testnet and account_type or reset to defaults
                            setValue("exchangeSettings.testnet", false); 
                            setValue("exchangeSettings.account_type", "");
                        } else {
                            useNotificationStore.getState().showNotification("Please enter both API Key and Secret Key.", 'warning');
                        }
                    }}
                >
                    Save API Keys
                </Button>
            </Paper>
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
                        // timer_start_condition is the only string field in this config
                        const isStringField = key === 'timer_start_condition';

                        if (isBoolean) {
                          return (
                            <FormControlLabel
                              control={
                                <Checkbox
                                  checked={!!field.value}
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
                            type={isStringField ? 'text' : 'number'}
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
            
            <Box sx={{ mb: 4 }}>
              <Grid container spacing={2}>
                <Grid size={{ xs: 12, md: 6 }}>
                  <Controller
                    name="dcaGridConfig.tp_mode"
                    control={control}
                    render={({ field }) => (
                      <TextField
                        {...field}
                        select
                        label="Take Profit Mode"
                        fullWidth
                        margin="normal"
                        error={!!errors.dcaGridConfig?.tp_mode}
                        helperText={errors.dcaGridConfig?.tp_mode?.message}
                        SelectProps={{ native: true }}
                      >
                        <option value="per_leg">Per Leg</option>
                        <option value="aggregate">Aggregate</option>
                        <option value="hybrid">Hybrid</option>
                      </TextField>
                    )}
                  />
                </Grid>
                <Grid size={{ xs: 12, md: 6 }}>
                  <Controller
                    name="dcaGridConfig.tp_aggregate_percent"
                    control={control}
                    render={({ field }) => (
                      <TextField
                        {...field}
                        label="Aggregate TP %"
                        fullWidth
                        margin="normal"
                        type="number"
                        inputProps={{ step: '0.01' }}
                        error={!!errors.dcaGridConfig?.tp_aggregate_percent}
                        helperText={errors.dcaGridConfig?.tp_aggregate_percent?.message}
                      />
                    )}
                  />
                </Grid>
              </Grid>
            </Box>

            {dcaFields.map((field, index) => (
              <Paper elevation={1} sx={{ p: 2, mb: 2 }} key={field.id}>
                <Grid container spacing={2} alignItems="center">
                  <Grid size={{ xs: 12, sm: 3 }}>
                    <Controller
                      name={`dcaGridConfig.levels.${index}.gap_percent`}
                      control={control}
                      render={({ field }) => (
                        <TextField
                          {...field}
                          label="Gap %"
                          fullWidth
                          margin="normal"
                          type="number"
                          inputProps={{ step: 'any' }}
                          onChange={(e) => field.onChange(e.target.value)}
                          error={!!errors.dcaGridConfig?.levels?.[index]?.gap_percent}
                          helperText={errors.dcaGridConfig?.levels?.[index]?.gap_percent?.message}
                        />
                      )}
                    />
                  </Grid>
                  <Grid size={{ xs: 12, sm: 3 }}>
                    <Controller
                      name={`dcaGridConfig.levels.${index}.weight_percent`}
                      control={control}
                      render={({ field }) => (
                        <TextField
                          {...field}
                          label="Weight %"
                          fullWidth
                          margin="normal"
                          type="number"
                          inputProps={{ step: 'any' }}
                          onChange={(e) => field.onChange(e.target.value)}
                          error={!!errors.dcaGridConfig?.levels?.[index]?.weight_percent}
                          helperText={errors.dcaGridConfig?.levels?.[index]?.weight_percent?.message}
                        />
                      )}
                    />
                  </Grid>
                  <Grid size={{ xs: 12, sm: 3 }}>
                    <Controller
                      name={`dcaGridConfig.levels.${index}.tp_percent`}
                      control={control}
                      render={({ field }) => (
                        <TextField
                          {...field}
                          label="TP %"
                          fullWidth
                          margin="normal"
                          type="number"
                          inputProps={{ step: 'any' }}
                          onChange={(e) => field.onChange(e.target.value)}
                          error={!!errors.dcaGridConfig?.levels?.[index]?.tp_percent}
                          helperText={errors.dcaGridConfig?.levels?.[index]?.tp_percent?.message}
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
            {errors.dcaGridConfig?.levels && (
                <Alert severity="error" sx={{ mt: 2 }}>
                    {(errors.dcaGridConfig.levels as any).root?.message}
                </Alert>
            )}
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
            <TextField
              label="Webhook URL"
              fullWidth
              margin="normal"
              value={settings?.id ? `${window.location.origin}/api/v1/webhooks/${settings.id}/tradingview` : 'Loading...'}
              InputProps={{
                readOnly: true,
              }}
              helperText="Copy this URL to your TradingView Alert Webhook settings."
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
                  disabled
                />
              )}
            />
          </CustomTabPanel>

          <CustomTabPanel value={currentTab} index={4}>
            <Typography variant="h6" gutterBottom>System Maintenance</Typography>
            <Box sx={{ mb: 3 }}>
                <Typography variant="subtitle1">Backup Configuration</Typography>
                <Typography variant="body2" color="text.secondary" paragraph>
                    Download a copy of your current configuration settings (excluding API keys).
                </Typography>
                <Button variant="outlined" onClick={() => {
                    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(settings, null, 2));
                    const downloadAnchorNode = document.createElement('a');
                    downloadAnchorNode.setAttribute("href",     dataStr);
                    downloadAnchorNode.setAttribute("download", "gemini_config_backup.json");
                    document.body.appendChild(downloadAnchorNode);
                    downloadAnchorNode.click();
                    downloadAnchorNode.remove();
                }}>
                    Download Backup
                </Button>
            </Box>
            
            <Divider sx={{ my: 3 }} />
            
            <Box sx={{ mb: 3 }}>
                <Typography variant="subtitle1">Restore Configuration</Typography>
                <Typography variant="body2" color="text.secondary" paragraph>
                    Restore settings from a backup file. This will overwrite current Risk and DCA configurations.
                </Typography>
                <Button
                    variant="contained"
                    component="label"
                >
                    Upload Backup File
                    <input
                        type="file"
                        hidden
                        accept=".json"
                        onChange={(event) => {
                            const fileReader = new FileReader();
                            if (event.target.files && event.target.files.length > 0) {
                                fileReader.readAsText(event.target.files[0], "UTF-8");
                                fileReader.onload = async (e) => {
                                    if (e.target?.result) {
                                        try {
                                            const parsed = JSON.parse(e.target.result as string);
                                            const payload: any = {
                                                username: parsed.username,
                                                email: parsed.email,
                                                exchange: parsed.exchange,
                                                risk_config: parsed.risk_config,
                                                dca_grid_config: parsed.dca_grid_config,
                                            };
                                            await updateSettings(payload);
                                            useNotificationStore.getState().showNotification("Configuration restored successfully.", "success");
                                        } catch (err) {
                                            console.error("Restore failed", err);
                                            useNotificationStore.getState().showNotification("Failed to parse configuration file.", "error");
                                        }
                                    }
                                };
                            }
                        }}
                    />
                </Button>
            </Box>
          </CustomTabPanel>
          
          <Button type="submit" variant="contained" color="success" sx={{ mt: 3 }} size="large">
            Save Settings
          </Button>
        </form>
      </Paper>
    </Box>
  );
};

export default SettingsPage;