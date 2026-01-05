import React, { useEffect, useState } from 'react';
import {
  Box,
  Button,
  Typography,
  Alert,
  Tabs,
  Tab,
  Grid,
  Card,
  CardContent,
} from '@mui/material';
import { useForm, Resolver, FieldErrors } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import SaveIcon from '@mui/icons-material/Save';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import SecurityIcon from '@mui/icons-material/Security';
import NotificationsIcon from '@mui/icons-material/Notifications';
import SettingsIcon from '@mui/icons-material/Settings';
import useConfigStore from '../store/configStore';
import useConfirmStore from '../store/confirmStore';
import useNotificationStore from '../store/notificationStore';
import QueuePrioritySettings from '../components/QueuePrioritySettings';
import DCAConfigList from '../components/dca_config/DCAConfigList';
import TelegramSettings from '../components/TelegramSettings';
import { MetricCard } from '../components/MetricCard';
import {
  SettingsPageSkeleton,
  ApiKeysListCard,
  ApiKeysFormCard,
  RiskLimitsSection,
  TimerConfigSection,
  AccountSettingsCard,
  BackupRestoreCard,
  SettingsSectionCard,
} from '../components/settings';
import type { BackupData } from '../components/settings/BackupRestoreCard';
import type { UserSettings } from '../store/configStore';
import type {
  DCAConfiguration,
  DCAConfigurationCreate,
  DCAConfigurationUpdate,
  EntryOrderType,
  TPMode,
  TPSettings
} from '../api/dcaConfig';

// Type for settings update payload with optional API key fields
interface SettingsUpdatePayload extends Partial<UserSettings> {
  api_key?: string;
  secret_key?: string;
  key_target_exchange?: string;
  testnet?: boolean;
  account_type?: string;
}

// BackupData type is imported from BackupRestoreCard

// Zod Schemas
const telegramConfigSchema = z.object({
  // Connection
  enabled: z.boolean(),
  bot_token: z.string().optional(),
  channel_id: z.string().optional(),
  channel_name: z.string().default('AlgoMakers.Ai Signals'),
  engine_signature: z.string().default(''),

  // Message Type Toggles
  send_entry_signals: z.boolean(),
  send_exit_signals: z.boolean(),
  send_status_updates: z.boolean(),
  send_dca_fill_updates: z.boolean(),
  send_pyramid_updates: z.boolean(),
  send_tp_hit_updates: z.boolean(),
  send_failure_alerts: z.boolean(),
  send_risk_alerts: z.boolean(),

  // Advanced Controls
  update_existing_message: z.boolean(),
  update_on_pyramid: z.boolean(),
  show_unrealized_pnl: z.boolean(),
  show_invested_amount: z.boolean(),
  show_duration: z.boolean(),

  // Threshold Alerts
  alert_loss_threshold_percent: z.number().nullable().optional(),
  alert_profit_threshold_percent: z.number().nullable().optional(),

  // Quiet Hours
  quiet_hours_enabled: z.boolean(),
  quiet_hours_start: z.string().nullable().optional(),
  quiet_hours_end: z.string().nullable().optional(),
  quiet_hours_urgent_only: z.boolean(),

  // Test mode
  test_mode: z.boolean(),
});

const exchangeSettingsSchema = z.object({
  key_target_exchange: z.string(),
  api_key: z.string().optional(),
  secret_key: z.string().optional(),
  testnet: z.boolean().optional(),
  account_type: z.string().optional(),
}).refine(
  (data) => {
    // Only require key_target_exchange when api_key and secret_key are provided
    if (data.api_key && data.secret_key) {
      return data.key_target_exchange.length > 0;
    }
    return true;
  },
  {
    message: 'Target exchange is required when setting API keys',
    path: ['key_target_exchange']
  }
);

const priorityRulesSchema = z.object({
  priority_rules_enabled: z.object({
    same_pair_timeframe: z.boolean(),
    deepest_loss_percent: z.boolean(),
    highest_replacement: z.boolean(),
    fifo_fallback: z.boolean(),
  }),
  priority_order: z.array(z.string()),
});

const riskEngineConfigSchema = z.object({
  max_open_positions_global: z.coerce.number().min(0),
  max_open_positions_per_symbol: z.coerce.number().min(0),
  max_total_exposure_usd: z.coerce.number().min(0),
  max_realized_loss_usd: z.coerce.number().min(0),
  loss_threshold_percent: z.coerce.number().max(0),
  required_pyramids_for_timer: z.coerce.number().min(1).max(10),
  post_pyramids_wait_minutes: z.coerce.number().min(0),
  max_winners_to_combine: z.coerce.number().min(0),
  priority_rules: priorityRulesSchema.optional(),
});

const appSettingsSchema = z.object({
  username: z.string().min(1, 'Username is required'),
  email: z.string().email('Invalid email address'),
  webhook_secret: z.string().optional(),
});

const formSchema = z.object({
  exchangeSettings: exchangeSettingsSchema,
  riskEngineConfig: riskEngineConfigSchema,
  appSettings: appSettingsSchema,
  telegramSettings: telegramConfigSchema,
});

type FormValues = {
  exchangeSettings: z.infer<typeof exchangeSettingsSchema>;
  riskEngineConfig: z.infer<typeof riskEngineConfigSchema>;
  appSettings: z.infer<typeof appSettingsSchema>;
  telegramSettings: z.infer<typeof telegramConfigSchema>;
};

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
      style={{ width: '100%', maxWidth: '100%', overflowX: 'hidden' }}
      {...other}
    >
      {value === index && children}
    </div>
  );
}

const SettingsPage: React.FC = () => {
  const {
    settings,
    supportedExchanges,
    loading,
    error,
    fetchSettings,
    updateSettings,
    deleteKey,
    fetchSupportedExchanges,
  } = useConfigStore();
  const [currentTab, setCurrentTab] = useState(0);

  useEffect(() => {
    fetchSettings();
    fetchSupportedExchanges();
  }, [fetchSettings, fetchSupportedExchanges]);

  const {
    handleSubmit,
    control,
    reset,
    setValue,
    watch,
    getValues,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(formSchema) as Resolver<FormValues>,
    defaultValues: {
      exchangeSettings: {
        key_target_exchange: '',
        api_key: '',
        secret_key: '',
        testnet: false,
        account_type: '',
      },
      riskEngineConfig: settings?.risk_config || {
        max_open_positions_global: 10,
        max_open_positions_per_symbol: 1,
        max_total_exposure_usd: 10000,
        max_realized_loss_usd: 500,
        loss_threshold_percent: -1.5,
        required_pyramids_for_timer: 3,
        post_pyramids_wait_minutes: 15,
        max_winners_to_combine: 3,
        priority_rules: {
          priority_rules_enabled: {
            same_pair_timeframe: true,
            deepest_loss_percent: true,
            highest_replacement: true,
            fifo_fallback: true,
          },
          priority_order: ['same_pair_timeframe', 'deepest_loss_percent', 'highest_replacement', 'fifo_fallback'],
        },
      },
      appSettings: {
        username: settings?.username || '',
        email: settings?.email || '',
        webhook_secret: settings?.webhook_secret || '',
      },
      telegramSettings: {
        enabled: false,
        bot_token: '',
        channel_id: '',
        channel_name: 'AlgoMakers.Ai Signals',
        engine_signature: '',
        send_entry_signals: true,
        send_exit_signals: true,
        send_status_updates: true,
        send_dca_fill_updates: true,
        send_pyramid_updates: true,
        send_tp_hit_updates: true,
        send_failure_alerts: true,
        send_risk_alerts: true,
        update_existing_message: true,
        update_on_pyramid: true,
        show_unrealized_pnl: true,
        show_invested_amount: true,
        show_duration: true,
        alert_loss_threshold_percent: null,
        alert_profit_threshold_percent: null,
        quiet_hours_enabled: false,
        quiet_hours_start: null,
        quiet_hours_end: null,
        quiet_hours_urgent_only: true,
        test_mode: false,
      },
    },
  });

  useEffect(() => {
    if (settings) {
      reset({
        exchangeSettings: {
          key_target_exchange: '',
          api_key: '',
          secret_key: '',
          testnet: false,
          account_type: '',
        },
        riskEngineConfig: {
          ...settings.risk_config,
          priority_rules: settings.risk_config.priority_rules || {
            priority_rules_enabled: {
              same_pair_timeframe: true,
              deepest_loss_percent: true,
              highest_replacement: true,
              fifo_fallback: true,
            },
            priority_order: ['same_pair_timeframe', 'deepest_loss_percent', 'highest_replacement', 'fifo_fallback'],
          },
        },
        appSettings: {
          username: settings.username,
          email: settings.email,
          webhook_secret: settings.webhook_secret,
        },
        telegramSettings: {
          // Defaults merged with saved settings to handle new fields
          enabled: false,
          bot_token: '',
          channel_id: '',
          channel_name: 'AlgoMakers.Ai Signals',
          engine_signature: '',
          send_entry_signals: true,
          send_exit_signals: true,
          send_status_updates: true,
          send_dca_fill_updates: true,
          send_pyramid_updates: true,
          send_tp_hit_updates: true,
          send_failure_alerts: true,
          send_risk_alerts: true,
          update_existing_message: true,
          update_on_pyramid: true,
          show_unrealized_pnl: true,
          show_invested_amount: true,
          show_duration: true,
          alert_loss_threshold_percent: null,
          alert_profit_threshold_percent: null,
          quiet_hours_enabled: false,
          quiet_hours_start: null,
          quiet_hours_end: null,
          quiet_hours_urgent_only: true,
          test_mode: false,
          // Override with saved settings
          ...settings.telegram_config,
        },
      });
    }
  }, [settings, reset]);

  const handleTabChange = (_event: React.SyntheticEvent, newValue: number) => {
    setCurrentTab(newValue);
  };

  const onSubmit = async (data: FormValues) => {
    // Merge form risk_config with existing settings to preserve unedited fields
    const mergedRiskConfig = {
      ...settings?.risk_config,  // Preserve existing fields not in form
      ...data.riskEngineConfig,  // Override with form values
    };

    const payload: SettingsUpdatePayload = {
      risk_config: mergedRiskConfig,
      username: data.appSettings.username,
      email: data.appSettings.email,
      webhook_secret: data.appSettings.webhook_secret,
      telegram_config: data.telegramSettings,
    };

    if (data.exchangeSettings.api_key && data.exchangeSettings.secret_key) {
      payload.api_key = data.exchangeSettings.api_key;
      payload.secret_key = data.exchangeSettings.secret_key;
      payload.key_target_exchange = data.exchangeSettings.key_target_exchange;
      // Include testnet and account_type if provided
      if (data.exchangeSettings.testnet !== undefined) {
        payload.testnet = data.exchangeSettings.testnet;
      }
      if (data.exchangeSettings.account_type) {
        payload.account_type = data.exchangeSettings.account_type;
      }
    }

    await updateSettings(payload);
  };

  const onError = (errors: FieldErrors<FormValues>) => {
    console.error('Form validation errors:', errors);
    if (errors.exchangeSettings) {
      setCurrentTab(0);
    } else if (errors.riskEngineConfig) {
      setCurrentTab(1);
    } else if (errors.telegramSettings) {
      setCurrentTab(2);
    } else if (errors.appSettings) {
      setCurrentTab(3);
    }
  };

  const handleDeleteKey = async (exchange: string) => {
    const confirmed = await useConfirmStore.getState().requestConfirm({
      title: 'Delete API Keys',
      message: `Are you sure you want to delete API keys for ${exchange}?`,
      confirmText: 'Delete',
      cancelText: 'Cancel',
    });
    if (confirmed) {
      await deleteKey(exchange);
    }
  };

  const handleEditKey = (exchange: string) => {
    setValue('exchangeSettings.key_target_exchange', exchange);
    const exchangeDetails = settings?.configured_exchange_details?.[exchange];
    if (exchangeDetails) {
      setValue('exchangeSettings.testnet', exchangeDetails.testnet || false);
      setValue('exchangeSettings.account_type', exchangeDetails.account_type || '');
    }
  };

  const handleSaveApiKeys = async () => {
    const currentValues = watch('exchangeSettings');

    if (currentValues.api_key && currentValues.secret_key) {
      const payload: SettingsUpdatePayload = {
        key_target_exchange: currentValues.key_target_exchange,
        api_key: currentValues.api_key,
        secret_key: currentValues.secret_key,
      };
      if (currentValues.testnet !== undefined) {
        payload.testnet = currentValues.testnet;
      }
      if (currentValues.account_type) {
        payload.account_type = currentValues.account_type;
      }
      await updateSettings(payload);
      setValue('exchangeSettings.api_key', '');
      setValue('exchangeSettings.secret_key', '');
      setValue('exchangeSettings.testnet', false);
      setValue('exchangeSettings.account_type', '');
    } else {
      useNotificationStore.getState().showNotification('Please enter both API Key and Secret Key.', 'warning');
    }
  };

  const handleRestore = async (parsed: BackupData) => {
    // Cast risk_config to the expected type (validated by Zod schema in BackupRestoreCard)
    const payload: SettingsUpdatePayload = {
      risk_config: parsed.risk_config as UserSettings['risk_config'],
    };

    await updateSettings(payload);

    if (parsed.dca_configurations && Array.isArray(parsed.dca_configurations)) {
      const { dcaConfigApi } = await import('../api/dcaConfig');
      const existingConfigs = await dcaConfigApi.getAll();

      let createdCount = 0;
      let updatedCount = 0;

      for (const dcaConfig of parsed.dca_configurations) {
        // Convert backup timeframe (string or number) to number for comparison
        const timeframeNum = typeof dcaConfig.timeframe === 'number'
          ? dcaConfig.timeframe
          : parseInt(dcaConfig.timeframe, 10);
        const existing = existingConfigs.find(
          (c: DCAConfiguration) =>
            c.pair === dcaConfig.pair &&
            c.exchange === dcaConfig.exchange &&
            c.timeframe === timeframeNum
        );

        // DCA levels from backup already use correct field names (gap_percent, weight_percent, tp_percent)
        const dcaLevels = dcaConfig.dca_levels?.map(level => ({
          gap_percent: level.gap_percent,
          weight_percent: level.weight_percent,
          tp_percent: level.tp_percent ?? 0,
        }));

        const pyramidLevels = dcaConfig.pyramid_specific_levels
          ? Object.fromEntries(
              Object.entries(dcaConfig.pyramid_specific_levels).map(([key, levels]) => [
                key,
                levels.map(level => ({
                  gap_percent: level.gap_percent,
                  weight_percent: level.weight_percent,
                  tp_percent: level.tp_percent ?? 0,
                }))
              ])
            )
          : undefined;

        if (existing) {
          const updateData: DCAConfigurationUpdate = {
            entry_order_type: dcaConfig.entry_order_type as EntryOrderType | undefined,
            dca_levels: dcaLevels,
            pyramid_specific_levels: pyramidLevels,
            tp_mode: dcaConfig.tp_mode as TPMode | undefined,
            tp_settings: dcaConfig.tp_settings as TPSettings | undefined,
            max_pyramids: dcaConfig.max_pyramids,
            // Capital override settings
            use_custom_capital: dcaConfig.use_custom_capital,
            custom_capital_usd: dcaConfig.custom_capital_usd,
            pyramid_custom_capitals: dcaConfig.pyramid_custom_capitals,
          };
          await dcaConfigApi.update(existing.id, updateData);
          updatedCount++;
        } else {
          const createData: DCAConfigurationCreate = {
            pair: dcaConfig.pair,
            timeframe: timeframeNum,
            exchange: dcaConfig.exchange,
            entry_order_type: (dcaConfig.entry_order_type as EntryOrderType) ?? 'limit',
            dca_levels: dcaLevels ?? [],
            pyramid_specific_levels: pyramidLevels,
            tp_mode: (dcaConfig.tp_mode as TPMode) ?? 'per_leg',
            tp_settings: (dcaConfig.tp_settings as TPSettings) ?? {},
            max_pyramids: dcaConfig.max_pyramids,
            // Capital override settings
            use_custom_capital: dcaConfig.use_custom_capital,
            custom_capital_usd: dcaConfig.custom_capital_usd,
            pyramid_custom_capitals: dcaConfig.pyramid_custom_capitals,
          };
          await dcaConfigApi.create(createData);
          createdCount++;
        }
      }

      useNotificationStore
        .getState()
        .showNotification(
          `Configuration restored successfully. DCA configs: ${createdCount} created, ${updatedCount} updated.`,
          'success'
        );
    } else {
      useNotificationStore
        .getState()
        .showNotification('Configuration restored successfully (no DCA configs found in backup).', 'success');
    }
  };

  if (loading && !settings) {
    return <SettingsPageSkeleton />;
  }

  if (error) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="error">Error loading settings: {error}</Alert>
      </Box>
    );
  }

  // Use the backend API URL for webhooks (not frontend origin)
  const apiBaseUrl = process.env.REACT_APP_API_URL || process.env.REACT_APP_API_BASE_URL || `${window.location.origin}/api/v1`;
  const webhookUrl = settings?.id
    ? `${apiBaseUrl}/webhooks/${settings.id}/tradingview`
    : 'Loading...';

  const configuredExchanges = settings?.configured_exchanges || [];
  const telegramEnabled = settings?.telegram_config?.enabled || false;

  return (
    <Box sx={{ flexGrow: 1, p: { xs: 1.5, sm: 3 }, pb: { xs: 12, sm: 3 }, maxWidth: '100%', overflowX: 'hidden' }}>
      {/* Header */}
      <Box sx={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: { xs: 'flex-start', sm: 'center' },
        flexDirection: { xs: 'column', sm: 'row' },
        gap: 1,
        mb: 2
      }}>
        <Typography variant="h4" sx={{ fontSize: { xs: '1.5rem', sm: '2.125rem' } }}>
          Settings
        </Typography>
        <Typography variant="caption" color="text.secondary">
          {configuredExchanges.length > 0 ? `${configuredExchanges.length} exchange(s) configured` : 'No exchanges configured'}
        </Typography>
      </Box>

      <form onSubmit={handleSubmit(onSubmit, onError)} style={{ maxWidth: '100%', overflowX: 'hidden' }}>
        {/* Tabs */}
        <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2, mx: { xs: -1.5, sm: 0 } }}>
          <Tabs
            value={currentTab}
            onChange={handleTabChange}
            aria-label="settings tabs"
            variant="scrollable"
            scrollButtons="auto"
            allowScrollButtonsMobile
            sx={{
              '& .MuiTab-root': {
                fontSize: { xs: '0.75rem', sm: '0.875rem' },
                minWidth: { xs: 70, sm: 120 },
                px: { xs: 1, sm: 2 },
              }
            }}
          >
            <Tab
              icon={<TrendingUpIcon sx={{ fontSize: { xs: 18, sm: 20 } }} />}
              iconPosition="start"
              label="Trading"
              sx={{ minHeight: 48 }}
            />
            <Tab
              icon={<SecurityIcon sx={{ fontSize: { xs: 18, sm: 20 } }} />}
              iconPosition="start"
              label="Risk"
              sx={{ minHeight: 48 }}
            />
            <Tab
              icon={<NotificationsIcon sx={{ fontSize: { xs: 18, sm: 20 } }} />}
              iconPosition="start"
              label="Alerts"
              sx={{ minHeight: 48 }}
            />
            <Tab
              icon={<SettingsIcon sx={{ fontSize: { xs: 18, sm: 20 } }} />}
              iconPosition="start"
              label="Account"
              sx={{ minHeight: 48 }}
            />
          </Tabs>
        </Box>
            {/* Tab 1: Trading */}
            <TabPanel value={currentTab} index={0}>
              {/* Exchange Configuration - Side by Side */}
              <Grid container spacing={{ xs: 1.5, sm: 3 }} sx={{ mb: { xs: 1.5, sm: 3 } }}>
                <Grid size={{ xs: 12, md: 6 }}>
                  <ApiKeysListCard
                    configuredExchanges={configuredExchanges}
                    exchangeDetails={settings?.configured_exchange_details || {}}
                    onEdit={handleEditKey}
                    onDelete={handleDeleteKey}
                  />
                </Grid>

                <Grid size={{ xs: 12, md: 6 }}>
                  <ApiKeysFormCard
                    control={control}
                    watch={watch}
                    supportedExchanges={supportedExchanges}
                    configuredExchanges={configuredExchanges}
                    onSaveKeys={handleSaveApiKeys}
                    errors={errors}
                  />
                </Grid>
              </Grid>

              {/* DCA Configurations */}
              <Grid container spacing={{ xs: 1.5, sm: 3 }}>
                <Grid size={12}>
                  <SettingsSectionCard
                    title="DCA Configurations"
                    icon={<TrendingUpIcon />}
                    description="Configure DCA levels for your trading pairs"
                  >
                    <DCAConfigList />
                  </SettingsSectionCard>
                </Grid>
              </Grid>
            </TabPanel>

            {/* Tab 2: Risk & Queue */}
            <TabPanel value={currentTab} index={1}>
              {/* Summary Cards */}
              <Grid container spacing={{ xs: 2, sm: 3 }} sx={{ mb: 3 }}>
                <Grid size={{ xs: 6, md: 3 }}>
                  <MetricCard
                    label="Max Positions"
                    value={settings?.risk_config?.max_open_positions_global || 0}
                    subtitle="global limit"
                    variant="small"
                  />
                </Grid>
                <Grid size={{ xs: 6, md: 3 }}>
                  <MetricCard
                    label="Loss Limit"
                    value={`$${settings?.risk_config?.max_realized_loss_usd || 0}`}
                    subtitle="circuit breaker"
                    colorScheme="bearish"
                    variant="small"
                  />
                </Grid>
              </Grid>

              <Grid container spacing={{ xs: 2, sm: 3 }}>
                <Grid size={{ xs: 12, md: 6 }}>
                  <RiskLimitsSection control={control} errors={errors} />
                </Grid>

                <Grid size={{ xs: 12, md: 6 }}>
                  <TimerConfigSection control={control} errors={errors} />
                </Grid>

                <Grid size={12}>
                  <SettingsSectionCard
                    title="Queue Priority Rules"
                    icon={<SecurityIcon />}
                    description="Drag to reorder signal priority"
                  >
                    <QueuePrioritySettings control={control} setValue={setValue} watch={watch} />
                  </SettingsSectionCard>
                </Grid>
              </Grid>
            </TabPanel>

            {/* Tab 3: Notifications */}
            <TabPanel value={currentTab} index={2}>
              {/* Summary Cards */}
              <Grid container spacing={{ xs: 2, sm: 3 }} sx={{ mb: 3 }}>
                <Grid size={{ xs: 6, md: 3 }}>
                  <MetricCard
                    label="Telegram"
                    value={telegramEnabled ? 'Enabled' : 'Disabled'}
                    colorScheme={telegramEnabled ? 'bullish' : 'neutral'}
                    variant="small"
                  />
                </Grid>
              </Grid>

              <Grid container spacing={{ xs: 2, sm: 3 }}>
                <Grid size={12}>
                  <SettingsSectionCard
                    title="Telegram Configuration"
                    icon={<NotificationsIcon />}
                    description="Configure Telegram bot notifications"
                  >
                    <TelegramSettings control={control} watch={watch} getValues={getValues} />
                  </SettingsSectionCard>
                </Grid>

                <Grid size={12}>
                  <Card sx={{ bgcolor: 'action.disabledBackground', opacity: 0.6 }}>
                    <CardContent>
                      <Typography variant="h6" color="text.secondary" gutterBottom>
                        Other Channels
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        Discord, Email, and Webhook notifications coming soon...
                      </Typography>
                    </CardContent>
                  </Card>
                </Grid>
              </Grid>
            </TabPanel>

            {/* Tab 4: Account & System */}
            <TabPanel value={currentTab} index={3}>
              <Grid container spacing={{ xs: 2, sm: 3 }}>
                <Grid size={{ xs: 12, md: 6 }}>
                  <AccountSettingsCard
                    control={control}
                    errors={errors}
                    webhookUrl={webhookUrl}
                  />
                </Grid>

                <Grid size={{ xs: 12, md: 6 }}>
                  <BackupRestoreCard settings={settings} onRestore={handleRestore} />
                </Grid>

                <Grid size={12}>
                  <Card
                    sx={{
                      borderColor: 'error.main',
                      borderWidth: 1,
                      borderStyle: 'solid',
                    }}
                  >
                    <CardContent>
                      <Typography variant="h6" color="error" gutterBottom>
                        Danger Zone
                      </Typography>
                      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                        Actions here can have permanent effects. Proceed with caution.
                      </Typography>
                      <Button variant="outlined" color="error" disabled>
                        Reset All Settings
                      </Button>
                    </CardContent>
                  </Card>
                </Grid>
              </Grid>
            </TabPanel>

        {/* Save Button */}
        <Box
          sx={{
            display: 'flex',
            justifyContent: { xs: 'stretch', sm: 'flex-end' },
            position: { xs: 'fixed', sm: 'static' },
            bottom: { xs: 72, sm: 'auto' },
            left: { xs: 0, sm: 'auto' },
            right: { xs: 0, sm: 'auto' },
            bgcolor: 'background.paper',
            p: { xs: 1.5, sm: 0 },
            borderTop: { xs: 1, sm: 0 },
            borderColor: 'divider',
            zIndex: { xs: 1000, sm: 'auto' },
            boxShadow: { xs: '0 -2px 10px rgba(0,0,0,0.2)', sm: 'none' },
          }}
        >
          <Button
            type="submit"
            variant="contained"
            color="success"
            size="large"
            startIcon={<SaveIcon />}
            fullWidth
            sx={{ maxWidth: { sm: 200 } }}
          >
            Save Settings
          </Button>
        </Box>
      </form>
    </Box>
  );
};

export default SettingsPage;
