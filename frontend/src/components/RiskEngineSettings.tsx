import React from 'react';
import { useFormContext, Controller } from 'react-hook-form';
import { TextField, Box, Typography, Checkbox, FormControlLabel } from '@mui/material';
import { z } from 'zod';

const schema = z.object({
  lossThresholdPercent: z.number().min(-100).max(0),
  requiredPyramidsForTimer: z.number().min(1).max(10),
  postPyramidsWaitMinutes: z.number().min(0),
  maxWinnersToCombine: z.number().min(1).max(10),
  maxRealizedLossUsd: z.number().min(0),
  partialCloseEnabled: z.boolean(),
});

type RiskEngineFormInputs = z.infer<typeof schema>;

const RiskEngineSettings: React.FC = () => {
  const {
    control,
    formState: { errors },
  } = useFormContext<RiskEngineFormInputs>();

  return (
    <Box sx={{ mt: 1 }}>
      <Typography variant="h6" gutterBottom>
        Risk Engine Configuration
      </Typography>

      <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 2 }}>
        Timer starts when BOTH conditions are met: required pyramids filled AND loss threshold exceeded.
      </Typography>

      <Controller
        name="lossThresholdPercent"
        control={control}
        render={({ field }) => (
          <TextField
            {...field}
            label="Loss Threshold (%)"
            variant="outlined"
            margin="normal"
            fullWidth
            type="number"
            error={!!errors.lossThresholdPercent}
            helperText={errors.lossThresholdPercent?.message || "e.g., -1.5 means timer starts when loss exceeds -1.5%"}
            onChange={(e) => field.onChange(parseFloat(e.target.value))}
          />
        )}
      />

      <Controller
        name="requiredPyramidsForTimer"
        control={control}
        render={({ field }) => (
          <TextField
            {...field}
            label="Required Pyramids for Timer"
            variant="outlined"
            margin="normal"
            fullWidth
            type="number"
            error={!!errors.requiredPyramidsForTimer}
            helperText={errors.requiredPyramidsForTimer?.message || "Number of pyramids (with all DCAs filled) required before timer can start"}
            onChange={(e) => field.onChange(parseInt(e.target.value, 10))}
          />
        )}
      />

      <Controller
        name="postPyramidsWaitMinutes"
        control={control}
        render={({ field }) => (
          <TextField
            {...field}
            label="Wait Time After Conditions Met (Minutes)"
            variant="outlined"
            margin="normal"
            fullWidth
            type="number"
            error={!!errors.postPyramidsWaitMinutes}
            helperText={errors.postPyramidsWaitMinutes?.message || "Timer countdown duration before offset execution"}
            onChange={(e) => field.onChange(parseInt(e.target.value, 10))}
          />
        )}
      />

      <Controller
        name="maxWinnersToCombine"
        control={control}
        render={({ field }) => (
          <TextField
            {...field}
            label="Max Winners to Combine"
            variant="outlined"
            margin="normal"
            fullWidth
            type="number"
            error={!!errors.maxWinnersToCombine}
            helperText={errors.maxWinnersToCombine?.message || "Maximum winning positions to partially close for offset"}
            onChange={(e) => field.onChange(parseInt(e.target.value, 10))}
          />
        )}
      />

      <Controller
        name="maxRealizedLossUsd"
        control={control}
        render={({ field }) => (
          <TextField
            {...field}
            label="Max Realized Loss (USD)"
            variant="outlined"
            margin="normal"
            fullWidth
            type="number"
            error={!!errors.maxRealizedLossUsd}
            helperText={errors.maxRealizedLossUsd?.message || "Queue stops releasing trades when this limit is reached"}
            onChange={(e) => field.onChange(parseFloat(e.target.value))}
          />
        )}
      />

      <Controller
        name="partialCloseEnabled"
        control={control}
        render={({ field }) => (
          <FormControlLabel
            control={<Checkbox {...field} checked={field.value} />}
            label="Enable Partial Close of Winners"
          />
        )}
      />
    </Box>
  );
};

export default RiskEngineSettings;
