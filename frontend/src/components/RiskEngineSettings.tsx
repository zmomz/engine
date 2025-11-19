import React from 'react';
import { useFormContext, Controller } from 'react-hook-form';
import { TextField, Box, Typography, Checkbox, FormControlLabel, Select, MenuItem, FormControl, InputLabel } from '@mui/material';
import { z } from 'zod';

const schema = z.object({
  lossThresholdPercent: z.number().min(-100).max(0),
  useTradeAgeFilter: z.boolean(),
  ageThresholdMinutes: z.number().min(0),
  requireFullPyramids: z.boolean(),
  postFullWaitMinutes: z.number().min(0),
  timerStartCondition: z.string(),
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
            helperText={errors.lossThresholdPercent?.message}
            onChange={(e) => field.onChange(parseFloat(e.target.value))}
          />
        )}
      />
      <Controller
        name="useTradeAgeFilter"
        control={control}
        render={({ field }) => (
          <FormControlLabel
            control={<Checkbox {...field} checked={field.value} />}
            label="Use Trade Age Filter"
          />
        )}
      />
      <Controller
        name="ageThresholdMinutes"
        control={control}
        render={({ field }) => (
          <TextField
            {...field}
            label="Age Threshold (Minutes)"
            variant="outlined"
            margin="normal"
            fullWidth
            type="number"
            error={!!errors.ageThresholdMinutes}
            helperText={errors.ageThresholdMinutes?.message}
            onChange={(e) => field.onChange(parseInt(e.target.value, 10))}
          />
        )}
      />
      <Controller
        name="requireFullPyramids"
        control={control}
        render={({ field }) => (
          <FormControlLabel
            control={<Checkbox {...field} checked={field.value} />}
            label="Require Full Pyramids"
          />
        )}
      />
      <Controller
        name="postFullWaitMinutes"
        control={control}
        render={({ field }) => (
          <TextField
            {...field}
            label="Post-Full Wait (Minutes)"
            variant="outlined"
            margin="normal"
            fullWidth
            type="number"
            error={!!errors.postFullWaitMinutes}
            helperText={errors.postFullWaitMinutes?.message}
            onChange={(e) => field.onChange(parseInt(e.target.value, 10))}
          />
        )}
      />
      <FormControl fullWidth margin="normal">
        <InputLabel id="timer-start-condition-label">Timer Start Condition</InputLabel>
        <Controller
          name="timerStartCondition"
          control={control}
          render={({ field }) => (
            <Select
              {...field}
              labelId="timer-start-condition-label"
              label="Timer Start Condition"
            >
              <MenuItem value="after_5_pyramids">After 5 Pyramids</MenuItem>
              <MenuItem value="after_all_dca_submitted">After All DCA Submitted</MenuItem>
              <MenuItem value="after_all_dca_filled">After All DCA Filled</MenuItem>
            </Select>
          )}
        />
      </FormControl>
    </Box>
  );
};

export default RiskEngineSettings;
