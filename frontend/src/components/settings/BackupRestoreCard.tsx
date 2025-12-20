import React, { useState } from 'react';
import { Box, Button, Typography, Grid, Alert } from '@mui/material';
import BackupIcon from '@mui/icons-material/Backup';
import CloudDownloadIcon from '@mui/icons-material/CloudDownload';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import SettingsSectionCard from './SettingsSectionCard';
import useNotificationStore from '../../store/notificationStore';

interface BackupRestoreCardProps {
  settings: any;
  onRestore: (data: any) => Promise<void>;
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

    setIsRestoring(true);

    const reader = new FileReader();
    reader.onload = async (e) => {
      try {
        const parsed = JSON.parse(e.target?.result as string);
        await onRestore(parsed);
      } catch (err) {
        console.error('Restore failed', err);
        useNotificationStore.getState().showNotification('Failed to parse configuration file.', 'error');
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
