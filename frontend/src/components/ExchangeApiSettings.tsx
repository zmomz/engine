import React from 'react';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { TextField, Button, Box, Typography, Checkbox, FormControlLabel } from '@mui/material';

const schema = z.object({
  apiKey: z.string().min(1, 'API Key is required'),
  apiSecret: z.string().min(1, 'API Secret is required'),
  testnet: z.boolean(),
});

type ExchangeApiFormInputs = z.infer<typeof schema>;

const ExchangeApiSettings: React.FC = () => {
  const {
    control,
    handleSubmit,
    formState: { errors },
  } = useForm<ExchangeApiFormInputs>({
    resolver: zodResolver(schema),
    defaultValues: {
      apiKey: '',
      apiSecret: '',
      testnet: false,
    },
  });

  const onSubmit = (data: ExchangeApiFormInputs) => {
    console.log(data);
    // Here you would call the API to save the settings
  };

  return (
    <Box component="form" onSubmit={handleSubmit(onSubmit)} sx={{ mt: 1 }}>
      <Typography variant="h6" gutterBottom>
        Binance API Credentials
      </Typography>
      <Controller
        name="apiKey"
        control={control}
        render={({ field }) => (
          <TextField
            {...field}
            label="API Key"
            variant="outlined"
            margin="normal"
            fullWidth
            error={!!errors.apiKey}
            helperText={errors.apiKey?.message}
            type="password"
          />
        )}
      />
      <Controller
        name="apiSecret"
        control={control}
        render={({ field }) => (
          <TextField
            {...field}
            label="API Secret"
            variant="outlined"
            margin="normal"
            fullWidth
            error={!!errors.apiSecret}
            helperText={errors.apiSecret?.message}
            type="password"
          />
        )}
      />
      <Controller
        name="testnet"
        control={control}
        render={({ field }) => (
          <FormControlLabel
            control={<Checkbox {...field} checked={field.value} />}
            label="Testnet Mode"
          />
        )}
      />
      <Box sx={{ mt: 2 }}>
        <Button type="submit" variant="contained" color="primary">
          Save Settings
        </Button>
      </Box>
    </Box>
  );
};

export default ExchangeApiSettings;
