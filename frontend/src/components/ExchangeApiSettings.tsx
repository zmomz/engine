import React from 'react';
import { useFormContext, Controller } from 'react-hook-form';
import { TextField, Box, Typography, Checkbox, FormControlLabel } from '@mui/material';

const ExchangeApiSettings: React.FC = () => {
  const {
    control,
    formState: { errors },
  } = useFormContext();

  return (
    <Box sx={{ mt: 1 }}>
      <Typography variant="h6" gutterBottom>
        Webhook Settings
      </Typography>
      <Controller
        name="webhookSecret"
        control={control}
        render={({ field }) => (
          <TextField
            {...field}
            label="Webhook Secret"
            variant="outlined"
            margin="normal"
            fullWidth
            type="password"
          />
        )}
      />
      <Typography variant="h6" gutterBottom sx={{ mt: 2 }}>
        Binance API Credentials
      </Typography>
      <Controller
        name="encrypted_api_keys.binance.apiKey"
        control={control}
        render={({ field }) => (
          <TextField
            {...field}
            label="API Key"
            variant="outlined"
            margin="normal"
            fullWidth
            type="password"
          />
        )}
      />
      <Controller
        name="encrypted_api_keys.binance.apiSecret"
        control={control}
        render={({ field }) => (
          <TextField
            {...field}
            label="API Secret"
            variant="outlined"
            margin="normal"
            fullWidth
            type="password"
          />
        )}
      />
      <Controller
        name="encrypted_api_keys.binance.testnet"
        control={control}
        render={({ field }) => (
          <FormControlLabel
            control={<Checkbox {...field} checked={field.value} />}
            label="Testnet Mode"
          />
        )}
      />
    </Box>
  );
};

export default ExchangeApiSettings;

