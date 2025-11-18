import React from 'react';
import { useFormContext, Controller } from 'react-hook-form';
import { TextField, Box, Typography } from '@mui/material';

const ExecutionPoolSettings: React.FC = () => {
  const {
    control,
    formState: { errors },
  } = useFormContext();

  return (
    <Box sx={{ mt: 1 }}>
      <Typography variant="h6" gutterBottom>
        Execution Pool Configuration
      </Typography>
      <Controller
        name="maxOpenGroups"
        control={control}
        render={({ field }) => (
          <TextField
            {...field}
            label="Max Open Groups"
            variant="outlined"
            margin="normal"
            fullWidth
            type="number"
            error={!!errors.maxOpenGroups}
            helperText={errors.maxOpenGroups?.message}
            onChange={(e) => field.onChange(parseInt(e.target.value, 10))}
          />
        )}
      />
    </Box>
  );
};

export default ExecutionPoolSettings;

