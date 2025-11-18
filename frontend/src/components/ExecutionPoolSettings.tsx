import React from 'react';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { TextField, Button, Box, Typography } from '@mui/material';

const schema = z.object({
  maxOpenGroups: z.number().min(1, 'Must be at least 1'),
});

type ExecutionPoolFormInputs = z.infer<typeof schema>;

const ExecutionPoolSettings: React.FC = () => {
  const {
    control,
    handleSubmit,
    formState: { errors },
  } = useForm<ExecutionPoolFormInputs>({
    resolver: zodResolver(schema),
    defaultValues: {
      maxOpenGroups: 10,
    },
  });

  const onSubmit = (data: ExecutionPoolFormInputs) => {
    console.log(data);
  };

  return (
    <Box component="form" onSubmit={handleSubmit(onSubmit)} sx={{ mt: 1 }}>
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
      <Box sx={{ mt: 2 }}>
        <Button type="submit" variant="contained" color="primary">
          Save Pool Settings
        </Button>
      </Box>
    </Box>
  );
};

export default ExecutionPoolSettings;
