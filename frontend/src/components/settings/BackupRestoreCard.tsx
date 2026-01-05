import React, { useState } from 'react';
import { Box, Button, Typography, Grid, Alert } from '@mui/material';
import BackupIcon from '@mui/icons-material/Backup';
import CloudDownloadIcon from '@mui/icons-material/CloudDownload';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import SettingsSectionCard from './SettingsSectionCard';
import useNotificationStore from '../../store/notificationStore';
import { z } from 'zod';
import type { DCAConfiguration } from '../../api/dcaConfig';

// Schema for validating backup file structure
// DCA level fields:
// - gap_percent: deviation from entry price (0 or negative, e.g., 0, -1, -2, -3)
// - weight_percent: percentage of capital for this level (0-100, must sum to 100)
// - tp_percent: take profit percentage for this level (positive)
// Using z.coerce.number() to handle both string and number inputs from backup files
const dcaLevelSchema = z.object({
  gap_percent: z.coerce.number().max(0),  // Must be 0 or negative
  weight_percent: z.coerce.number().min(0).max(100),
  tp_percent: z.coerce.number().min(0).optional(),
});

const dcaConfigSchema = z.object({
  pair: z.string().min(1),
  timeframe: z.union([z.string().min(1), z.number()]),  // Accept both string and number
  exchange: z.string().min(1),
  entry_order_type: z.string().optional(),
  dca_levels: z.array(dcaLevelSchema).optional(),
  pyramid_specific_levels: z.record(z.array(dcaLevelSchema)).optional(),
  tp_mode: z.string().optional(),
  tp_settings: z.record(z.unknown()).optional(),
  max_pyramids: z.coerce.number().min(0).max(100).optional(),  // Allow 0 (no pyramids)
  // Capital override settings
  use_custom_capital: z.boolean().optional(),
  custom_capital_usd: z.coerce.number().min(0).optional(),
  pyramid_custom_capitals: z.record(z.coerce.number()).optional(),
});

const riskConfigSchema = z.object({
  max_open_positions_global: z.coerce.number().min(0).optional(),
  max_open_positions_per_symbol: z.coerce.number().min(0).optional(),
  max_total_exposure_usd: z.coerce.number().min(0).optional(),
  max_realized_loss_usd: z.coerce.number().optional(),
  loss_threshold_percent: z.coerce.number().optional(),
  required_pyramids_for_timer: z.coerce.number().min(0).optional(),
  post_pyramids_wait_minutes: z.coerce.number().min(0).optional(),
  max_winners_to_combine: z.coerce.number().min(0).optional(),
  priority_rules: z.object({
    priority_rules_enabled: z.object({
      same_pair_timeframe: z.boolean(),
      deepest_loss_percent: z.boolean(),
      highest_replacement: z.boolean(),
      fifo_fallback: z.boolean(),
    }).optional(),
    priority_order: z.array(z.string()).optional(),
  }).optional(),
}).optional();

const backupDataSchema = z.object({
  risk_config: riskConfigSchema,
  dca_configurations: z.array(dcaConfigSchema).optional(),
});

// Export type for use in parent components
export type BackupData = z.infer<typeof backupDataSchema>;

// Type for settings prop (matches UserSettings from authStore)
interface SettingsType {
  risk_config?: Record<string, unknown>;
}

interface BackupRestoreCardProps {
  settings: SettingsType | null;
  onRestore: (data: z.infer<typeof backupDataSchema>) => Promise<void>;
}

const BackupRestoreCard: React.FC<BackupRestoreCardProps> = ({
  settings,
  onRestore,
}) => {
  const [isRestoring, setIsRestoring] = useState(false);

  const handleBackup = async () => {
    try {
      const { dcaConfigApi } = await import('../../api/dcaConfig');
      const dcaConfigs = await dcaConfigApi.getAll();

      // Helper to convert string numbers to actual numbers for cleaner backup output
      const toNumber = (val: string | number | undefined): number | undefined => {
        if (val === undefined || val === null) return undefined;
        const num = typeof val === 'string' ? parseFloat(val) : val;
        return isNaN(num) ? undefined : num;
      };

      const convertDcaLevels = (levels: DCAConfiguration['dca_levels']) =>
        levels?.map(level => ({
          gap_percent: toNumber(level.gap_percent) ?? 0,
          weight_percent: toNumber(level.weight_percent) ?? 0,
          tp_percent: toNumber(level.tp_percent) ?? 0,
        }));

      const convertPyramidLevels = (levels: DCAConfiguration['pyramid_specific_levels']) => {
        if (!levels) return undefined;
        const result: Record<string, { gap_percent: number; weight_percent: number; tp_percent: number }[]> = {};
        for (const [key, value] of Object.entries(levels)) {
          result[key] = value.map(level => ({
            gap_percent: toNumber(level.gap_percent) ?? 0,
            weight_percent: toNumber(level.weight_percent) ?? 0,
            tp_percent: toNumber(level.tp_percent) ?? 0,
          }));
        }
        return result;
      };

      const backupData = {
        risk_config: settings?.risk_config,
        dca_configurations: dcaConfigs.map((config: DCAConfiguration) => ({
          pair: config.pair,
          timeframe: config.timeframe,
          exchange: config.exchange,
          entry_order_type: config.entry_order_type,
          dca_levels: convertDcaLevels(config.dca_levels),
          pyramid_specific_levels: convertPyramidLevels(config.pyramid_specific_levels),
          tp_mode: config.tp_mode,
          tp_settings: config.tp_settings,
          max_pyramids: config.max_pyramids,
          // Capital override settings
          use_custom_capital: config.use_custom_capital,
          custom_capital_usd: toNumber(config.custom_capital_usd),
          pyramid_custom_capitals: config.pyramid_custom_capitals
            ? Object.fromEntries(
                Object.entries(config.pyramid_custom_capitals).map(([k, v]) => [k, toNumber(v) ?? 0])
              )
            : undefined,
        })),
      };

      const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(backupData, null, 2));
      const downloadAnchorNode = document.createElement('a');
      downloadAnchorNode.setAttribute('href', dataStr);
      downloadAnchorNode.setAttribute('download', `config_backup_${new Date().toISOString().split('T')[0]}.json`);
      document.body.appendChild(downloadAnchorNode);
      downloadAnchorNode.click();
      downloadAnchorNode.remove();

      useNotificationStore.getState().showNotification('Backup downloaded successfully with DCA configurations.', 'success');
    } catch (err) {
      console.error('Backup failed', err);
      useNotificationStore.getState().showNotification('Failed to create backup: ' + (err as Error).message, 'error');
    }
  };

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    // Validate file size (max 1MB)
    const MAX_FILE_SIZE = 1024 * 1024; // 1MB
    if (file.size > MAX_FILE_SIZE) {
      useNotificationStore.getState().showNotification('File too large. Maximum size is 1MB.', 'error');
      event.target.value = '';
      return;
    }

    setIsRestoring(true);

    const reader = new FileReader();
    reader.onload = async (e) => {
      try {
        const content = e.target?.result as string;

        // Parse JSON
        let parsed: unknown;
        try {
          parsed = JSON.parse(content);
        } catch {
          throw new Error('Invalid JSON format');
        }

        // Validate against schema
        const validationResult = backupDataSchema.safeParse(parsed);
        if (!validationResult.success) {
          const errors = validationResult.error.errors
            .map((err) => `${err.path.join('.')}: ${err.message}`)
            .slice(0, 3) // Show max 3 errors
            .join('; ');
          throw new Error(`Invalid backup format: ${errors}`);
        }

        await onRestore(validationResult.data);
      } catch (err) {
        console.error('Restore failed', err);
        const message = err instanceof Error ? err.message : 'Failed to parse configuration file.';
        useNotificationStore.getState().showNotification(message, 'error');
      } finally {
        setIsRestoring(false);
      }
    };
    reader.readAsText(file, 'UTF-8');

    // Reset input so same file can be selected again
    event.target.value = '';
  };

  return (
    <SettingsSectionCard
      title="Backup & Restore"
      icon={<BackupIcon />}
      description="Export or import your configuration"
    >
      <Grid container spacing={{ xs: 1.5, sm: 3 }}>
        <Grid size={{ xs: 12, sm: 6 }}>
          <Box
            sx={{
              p: { xs: 1.5, sm: 2 },
              borderRadius: 1,
              bgcolor: 'background.default',
              height: '100%',
            }}
          >
            <Typography variant="subtitle2" gutterBottom sx={{ fontSize: { xs: '0.8rem', sm: '0.875rem' } }}>
              Download Backup
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5, fontSize: { xs: '0.7rem', sm: '0.8rem' } }}>
              Export config and DCA settings (no API keys).
            </Typography>
            <Button
              variant="outlined"
              startIcon={<CloudDownloadIcon />}
              onClick={handleBackup}
              fullWidth
              size="small"
            >
              Download
            </Button>
          </Box>
        </Grid>

        <Grid size={{ xs: 12, sm: 6 }}>
          <Box
            sx={{
              p: { xs: 1.5, sm: 2 },
              borderRadius: 1,
              bgcolor: 'background.default',
              height: '100%',
            }}
          >
            <Typography variant="subtitle2" gutterBottom sx={{ fontSize: { xs: '0.8rem', sm: '0.875rem' } }}>
              Restore Configuration
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5, fontSize: { xs: '0.7rem', sm: '0.8rem' } }}>
              Overwrites Risk and DCA settings.
            </Typography>
            <Button
              variant="contained"
              component="label"
              startIcon={<CloudUploadIcon />}
              disabled={isRestoring}
              fullWidth
              size="small"
            >
              {isRestoring ? 'Restoring...' : 'Upload'}
              <input
                type="file"
                hidden
                accept=".json"
                onChange={handleFileUpload}
              />
            </Button>
          </Box>
        </Grid>
      </Grid>

      <Alert severity="warning" sx={{ mt: 2, py: { xs: 0.5, sm: 1 }, '& .MuiAlert-message': { fontSize: { xs: '0.7rem', sm: '0.875rem' } } }}>
        Restore overwrites Risk and DCA settings. API keys are unaffected.
      </Alert>
    </SettingsSectionCard>
  );
};

export default BackupRestoreCard;
