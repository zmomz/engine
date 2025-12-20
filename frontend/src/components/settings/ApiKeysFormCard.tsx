import React from 'react';
import {
  Box,
  TextField,
  Button,
  Alert,
  FormControlLabel,
  Checkbox,
  Grid,
} from '@mui/material';
import { Control, Controller, UseFormWatch } from 'react-hook-form';
import AddIcon from '@mui/icons-material/Add';
import SettingsSectionCard from './SettingsSectionCard';

interface ApiKeysFormCardProps {
  control: Control<any>;
  watch: UseFormWatch<any>;
  supportedExchanges: string[];
  configuredExchanges: string[];
  onSaveKeys: () => void;
  errors?: any;
}

const ApiKeysFormCard: React.FC<ApiKeysFormCardProps> = ({
  control,
  watch,
  supportedExchanges,
  configuredExchanges,
  onSaveKeys,
  errors,
}) => {
  const selectedExchange = watch('exchangeSettings.key_target_exchange');
  const isConfigured = configuredExchanges.includes(selectedExchange);

  return (
    <SettingsSectionCard
      title="Add API Keys"
      icon={<AddIcon />}
      description="Configure API credentials for an exchange"
    >
      <Grid container spacing={{ xs: 1.5, sm: 2 }}>
        <Grid size={{ xs: 6, sm: 6 }}>
          <Controller
            name="exchangeSettings.key_target_exchange"
            control={control}
            render={({ field }) => (
              <TextField
                {...field}
                select
                label="Exchange"
                fullWidth
                size="small"
                SelectProps={{ native: true }}
                error={!!errors?.exchangeSettings?.key_target_exchange}
              >
                {supportedExchanges.map((exchange) => (
                  <option key={exchange} value={exchange}>
                    {exchange}
                  </option>
                ))}
              </TextField>
            )}
          />
        </Grid>

        <Grid size={{ xs: 6, sm: 6 }}>
          <Controller
            name="exchangeSettings.account_type"
            control={control}
            render={({ field }) => (
              <TextField
                {...field}
                label="Account Type"
                fullWidth
                size="small"
                placeholder="UNIFIED"
              />
            )}
          />
        </Grid>

        {selectedExchange && !isConfigured && (
          <Grid size={12}>
            <Alert severity="warning" sx={{ py: 0.5, fontSize: '0.75rem' }}>
              No keys found for {selectedExchange}
            </Alert>
          </Grid>
        )}

        <Grid size={{ xs: 12, sm: 6 }}>
          <Controller
            name="exchangeSettings.api_key"
            control={control}
            render={({ field }) => (
              <TextField
                {...field}
                label="API Key"
                fullWidth
                size="small"
                error={!!errors?.exchangeSettings?.api_key}
              />
            )}
          />
        </Grid>

        <Grid size={{ xs: 12, sm: 6 }}>
          <Controller
            name="exchangeSettings.secret_key"
            control={control}
            render={({ field }) => (
              <TextField
                {...field}
                label="Secret Key"
                fullWidth
                size="small"
                type="password"
                error={!!errors?.exchangeSettings?.secret_key}
              />
            )}
          />
        </Grid>

        <Grid size={12}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 1 }}>
            <Controller
              name="exchangeSettings.testnet"
              control={control}
              render={({ field }) => (
                <FormControlLabel
                  control={
                    <Checkbox
                      checked={!!field.value}
                      onChange={(e) => field.onChange(e.target.checked)}
                      size="small"
                    />
                  }
                  label={<Box component="span" sx={{ fontSize: '0.85rem' }}>Testnet</Box>}
                  sx={{ mr: 0 }}
                />
              )}
            />

            <Button
              variant="contained"
              color="primary"
              onClick={onSaveKeys}
              size="small"
              sx={{ minWidth: { xs: 80, sm: 120 } }}
            >
              Save
            </Button>
          </Box>
        </Grid>
      </Grid>
    </SettingsSectionCard>
  );
};

export default ApiKeysFormCard;
