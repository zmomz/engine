import React from 'react';
import { TextField, Chip, Alert } from '@mui/material';
import { Control, Controller } from 'react-hook-form';
import LinkIcon from '@mui/icons-material/Link';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import SettingsSectionCard from './SettingsSectionCard';

interface ExchangeConnectionCardProps {
  control: Control<any>;
  supportedExchanges: string[];
  configuredExchanges: string[];
  activeExchange: string;
}

const ExchangeConnectionCard: React.FC<ExchangeConnectionCardProps> = ({
  control,
  supportedExchanges,
  configuredExchanges,
  activeExchange,
}) => {
  const isConnected = configuredExchanges.includes(activeExchange);

  return (
    <SettingsSectionCard
      title="Exchange"
      icon={<LinkIcon />}
      description="Select your active trading exchange"
      action={
        <Chip
          icon={isConnected ? <CheckCircleIcon /> : undefined}
          label={isConnected ? "Connected" : "Not Connected"}
          color={isConnected ? "success" : "warning"}
          size="small"
          variant="outlined"
          sx={{ height: 24, fontSize: '0.7rem' }}
        />
      }
    >
      <Controller
        name="exchangeSettings.exchange"
        control={control}
        render={({ field }) => (
          <TextField
            {...field}
            select
            label="Active Exchange"
            fullWidth
            size="small"
            SelectProps={{ native: true }}
          >
            {supportedExchanges.map((exchange) => (
              <option key={exchange} value={exchange}>
                {exchange} {configuredExchanges.includes(exchange) ? '✓' : ''}
              </option>
            ))}
          </TextField>
        )}
      />

      {!isConnected && (
        <Alert severity="warning" sx={{ mt: 1.5, py: 0.5, fontSize: '0.75rem' }}>
          No API keys configured for this exchange
        </Alert>
      )}
    </SettingsSectionCard>
  );
};

export default ExchangeConnectionCard;
