import React from 'react';
import { TextField, Grid, Alert } from '@mui/material';
import { Control, Controller, FieldErrors } from 'react-hook-form';
import SecurityIcon from '@mui/icons-material/Security';
import SettingsSectionCard from './SettingsSectionCard';

interface RiskLimitsSectionProps {
  control: Control<any>;
  errors?: FieldErrors<any>;
}

const RiskLimitsSection: React.FC<RiskLimitsSectionProps> = ({ control, errors }) => {
  const riskErrors = (errors as any)?.riskEngineConfig;

  return (
    <SettingsSectionCard
      title="Pre-Trade Risk Limits"
      icon={<SecurityIcon />}
      description="Configure position and exposure limits"
    >
      <Alert severity="info" sx={{ mb: 2, py: { xs: 0.5, sm: 1 }, '& .MuiAlert-message': { fontSize: { xs: '0.7rem', sm: '0.875rem' } } }}>
        Limits checked before opening positions. Queue stops when limits are reached.
      </Alert>

      <Grid container spacing={{ xs: 1.5, sm: 2 }}>
        <Grid size={{ xs: 12, sm: 6 }}>
          <Controller
            name="riskEngineConfig.max_open_positions_global"
            control={control}
            render={({ field }) => (
              <TextField
                {...field}
                label="Max Positions (Global)"
                fullWidth
                size="small"
                type="number"
                inputProps={{ step: 1, min: 0 }}
                onChange={(e) => field.onChange(e.target.value)}
                error={!!riskErrors?.max_open_positions_global}
                helperText={riskErrors?.max_open_positions_global?.message || 'Max total positions'}
                sx={{ '& .MuiFormHelperText-root': { fontSize: { xs: '0.65rem', sm: '0.75rem' } } }}
              />
            )}
          />
        </Grid>

        <Grid size={{ xs: 12, sm: 6 }}>
          <Controller
            name="riskEngineConfig.max_open_positions_per_symbol"
            control={control}
            render={({ field }) => (
              <TextField
                {...field}
                label="Max Per Symbol"
                fullWidth
                size="small"
                type="number"
                inputProps={{ step: 1, min: 0 }}
                onChange={(e) => field.onChange(e.target.value)}
                error={!!riskErrors?.max_open_positions_per_symbol}
                helperText={riskErrors?.max_open_positions_per_symbol?.message || 'Max per pair'}
                sx={{ '& .MuiFormHelperText-root': { fontSize: { xs: '0.65rem', sm: '0.75rem' } } }}
              />
            )}
          />
        </Grid>

        <Grid size={{ xs: 12, sm: 6 }}>
          <Controller
            name="riskEngineConfig.max_total_exposure_usd"
            control={control}
            render={({ field }) => (
              <TextField
                {...field}
                label="Max Exposure (USD)"
                fullWidth
                size="small"
                type="number"
                inputProps={{ step: 100, min: 0 }}
                onChange={(e) => field.onChange(e.target.value)}
                error={!!riskErrors?.max_total_exposure_usd}
                helperText={riskErrors?.max_total_exposure_usd?.message || 'Max capital deployed'}
                sx={{ '& .MuiFormHelperText-root': { fontSize: { xs: '0.65rem', sm: '0.75rem' } } }}
              />
            )}
          />
        </Grid>

        <Grid size={{ xs: 12, sm: 6 }}>
          <Controller
            name="riskEngineConfig.max_realized_loss_usd"
            control={control}
            render={({ field }) => (
              <TextField
                {...field}
                label="Loss Limit (USD)"
                fullWidth
                size="small"
                type="number"
                inputProps={{ step: 10, min: 0 }}
                onChange={(e) => field.onChange(e.target.value)}
                error={!!riskErrors?.max_realized_loss_usd}
                helperText={riskErrors?.max_realized_loss_usd?.message || 'Circuit breaker'}
                sx={{ '& .MuiFormHelperText-root': { fontSize: { xs: '0.65rem', sm: '0.75rem' } } }}
              />
            )}
          />
        </Grid>
      </Grid>
    </SettingsSectionCard>
  );
};

export default RiskLimitsSection;
