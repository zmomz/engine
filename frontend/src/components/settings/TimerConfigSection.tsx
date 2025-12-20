import React from 'react';
import { TextField, Grid, Alert } from '@mui/material';
import { Control, Controller, FieldErrors } from 'react-hook-form';
import TimerIcon from '@mui/icons-material/Timer';
import SettingsSectionCard from './SettingsSectionCard';

interface TimerConfigSectionProps {
  control: Control<any>;
  errors?: FieldErrors<any>;
}

const TimerConfigSection: React.FC<TimerConfigSectionProps> = ({ control, errors }) => {
  const riskErrors = (errors as any)?.riskEngineConfig;

  return (
    <SettingsSectionCard
      title="Timer Configuration"
      icon={<TimerIcon />}
      description="Offset execution timer settings"
    >
      <Alert severity="info" sx={{ mb: 2, py: { xs: 0.5, sm: 1 }, '& .MuiAlert-message': { fontSize: { xs: '0.7rem', sm: '0.875rem' } } }}>
        Timer starts when required pyramids filled AND loss threshold exceeded.
      </Alert>

      <Grid container spacing={{ xs: 1.5, sm: 2 }}>
        <Grid size={{ xs: 12, sm: 6 }}>
          <Controller
            name="riskEngineConfig.loss_threshold_percent"
            control={control}
            render={({ field }) => (
              <TextField
                {...field}
                label="Loss Threshold (%)"
                fullWidth
                size="small"
                type="number"
                inputProps={{ step: 0.1, max: 0 }}
                onChange={(e) => field.onChange(e.target.value)}
                error={!!riskErrors?.loss_threshold_percent}
                helperText={riskErrors?.loss_threshold_percent?.message || 'e.g., -1.5%'}
                sx={{ '& .MuiFormHelperText-root': { fontSize: { xs: '0.65rem', sm: '0.75rem' } } }}
              />
            )}
          />
        </Grid>

        <Grid size={{ xs: 12, sm: 6 }}>
          <Controller
            name="riskEngineConfig.required_pyramids_for_timer"
            control={control}
            render={({ field }) => (
              <TextField
                {...field}
                label="Pyramids for Timer"
                fullWidth
                size="small"
                type="number"
                inputProps={{ step: 1, min: 1, max: 10 }}
                onChange={(e) => field.onChange(e.target.value)}
                error={!!riskErrors?.required_pyramids_for_timer}
                helperText={riskErrors?.required_pyramids_for_timer?.message || 'Required before timer starts'}
                sx={{ '& .MuiFormHelperText-root': { fontSize: { xs: '0.65rem', sm: '0.75rem' } } }}
              />
            )}
          />
        </Grid>

        <Grid size={{ xs: 12, sm: 6 }}>
          <Controller
            name="riskEngineConfig.post_pyramids_wait_minutes"
            control={control}
            render={({ field }) => (
              <TextField
                {...field}
                label="Wait Time (min)"
                fullWidth
                size="small"
                type="number"
                inputProps={{ step: 1, min: 0 }}
                onChange={(e) => field.onChange(e.target.value)}
                error={!!riskErrors?.post_pyramids_wait_minutes}
                helperText={riskErrors?.post_pyramids_wait_minutes?.message || 'Countdown before offset'}
                sx={{ '& .MuiFormHelperText-root': { fontSize: { xs: '0.65rem', sm: '0.75rem' } } }}
              />
            )}
          />
        </Grid>

        <Grid size={{ xs: 12, sm: 6 }}>
          <Controller
            name="riskEngineConfig.max_winners_to_combine"
            control={control}
            render={({ field }) => (
              <TextField
                {...field}
                label="Max Winners"
                fullWidth
                size="small"
                type="number"
                inputProps={{ step: 1, min: 0 }}
                onChange={(e) => field.onChange(e.target.value)}
                error={!!riskErrors?.max_winners_to_combine}
                helperText={riskErrors?.max_winners_to_combine?.message || 'Winners for offset'}
                sx={{ '& .MuiFormHelperText-root': { fontSize: { xs: '0.65rem', sm: '0.75rem' } } }}
              />
            )}
          />
        </Grid>
      </Grid>
    </SettingsSectionCard>
  );
};

export default TimerConfigSection;
