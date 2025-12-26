import React, { useState } from 'react';
import { Box, Button, Typography, Grid, Alert } from '@mui/material';
import BackupIcon from '@mui/icons-material/Backup';
import CloudDownloadIcon from '@mui/icons-material/CloudDownload';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import SettingsSectionCard from './SettingsSectionCard';
import useNotificationStore from '../../store/notificationStore';
import { z } from 'zod';

// Schema for validating backup file structure
const dcaLevelSchema = z.object({
  percent_of_total: z.number().min(0).max(100),
  deviation_percent: z.number().min(0),
  tp_percent: z.number().min(0).optional(),
});

const dcaConfigSchema = z.object({
  pair: z.string().min(1),
  timeframe: z.string().min(1),
  exchange: z.string().min(1),
  entry_order_type: z.string().optional(),
  dca_levels: z.array(dcaLevelSchema).optional(),
  pyramid_specific_levels: z.record(z.array(dcaLevelSchema)).optional(),
  tp_mode: z.string().optional(),
  tp_settings: z.record(z.unknown()).optional(),
  max_pyramids: z.number().min(1).max(100).optional(),
});

const riskConfigSchema = z.object({
  max_open_positions_global: z.number().min(0).optional(),
  max_open_positions_per_symbol: z.number().min(0).optional(),
  max_total_exposure_usd: z.number().min(0).optional(),
  max_realized_loss_usd: z.number().optional(),
  loss_threshold_percent: z.number().optional(),
  required_pyramids_for_timer: z.number().min(0).optional(),
  post_pyramids_wait_minutes: z.number().min(0).optional(),
  max_winners_to_combine: z.number().min(0).optional(),
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
  exchange: z.string().optional(),
  risk_config: riskConfigSchema,
  dca_configurations: z.array(dcaConfigSchema).optional(),
});

// Type for settings prop (matches UserSettings from authStore)
interface SettingsType {
  exchange?: string;
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

      const backupData = {
        exchange: settings?.exchange,
        risk_config: settings?.risk_config,
        dca_configurations: dcaConfigs.map((config: any) => ({
          pair: config.pair,
          timeframe: config.timeframe,
          exchange: config.exchange,
          entry_order_type: config.entry_order_type,
          dca_levels: config.dca_levels,
          pyramid_specific_levels: config.pyramid_specific_levels,
          tp_mode: config.tp_mode,
          tp_settings: config.tp_settings,
          max_pyramids: config.max_pyramids,
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
