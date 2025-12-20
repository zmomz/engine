import React from 'react';
import {
  IconButton,
  Typography,
  Chip,
  Box,
} from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import EditIcon from '@mui/icons-material/Edit';
import VpnKeyIcon from '@mui/icons-material/VpnKey';
import SettingsSectionCard from './SettingsSectionCard';

interface ApiKeysListCardProps {
  configuredExchanges: string[];
  activeExchange: string;
  exchangeDetails?: Record<string, { testnet?: boolean; account_type?: string }>;
  onEdit: (exchange: string) => void;
  onDelete: (exchange: string) => void;
}

const ApiKeysListCard: React.FC<ApiKeysListCardProps> = ({
  configuredExchanges,
  activeExchange,
  exchangeDetails = {},
  onEdit,
  onDelete,
}) => {
  return (
    <SettingsSectionCard
      title="API Keys"
      icon={<VpnKeyIcon />}
      description={`${configuredExchanges.length} exchange(s) configured`}
    >
      {configuredExchanges.length > 0 ? (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
          {configuredExchanges.map((exchange) => {
            const details = exchangeDetails[exchange];
            const isActive = exchange === activeExchange;

            return (
              <Box
                key={exchange}
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  p: 1,
                  borderRadius: 1,
                  bgcolor: isActive ? 'action.selected' : 'background.default',
                  borderLeft: isActive ? 3 : 0,
                  borderColor: 'primary.main',
                }}
              >
                <Box sx={{ minWidth: 0, flex: 1 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, flexWrap: 'wrap' }}>
                    <Typography variant="body2" fontWeight={isActive ? 600 : 400} sx={{ fontSize: '0.85rem' }}>
                      {exchange}
                    </Typography>
                    {isActive && (
                      <Chip label="Active" size="small" color="primary" sx={{ height: 16, fontSize: '0.6rem' }} />
                    )}
                    {details?.testnet && (
                      <Chip label="Test" size="small" color="warning" variant="outlined" sx={{ height: 16, fontSize: '0.6rem' }} />
                    )}
                  </Box>
                  {details?.account_type && (
                    <Typography variant="caption" color="text.secondary">
                      {details.account_type}
                    </Typography>
                  )}
                </Box>
                <Box sx={{ display: 'flex', gap: 0.25, flexShrink: 0 }}>
                  <IconButton
                    aria-label="edit"
                    onClick={() => onEdit(exchange)}
                    size="small"
                    sx={{ p: 0.5 }}
                  >
                    <EditIcon sx={{ fontSize: 18 }} />
                  </IconButton>
                  <IconButton
                    aria-label="delete"
                    onClick={() => onDelete(exchange)}
                    color="error"
                    size="small"
                    sx={{ p: 0.5 }}
                  >
                    <DeleteIcon sx={{ fontSize: 18 }} />
                  </IconButton>
                </Box>
              </Box>
            );
          })}
        </Box>
      ) : (
        <Box sx={{ py: 2, textAlign: 'center' }}>
          <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.8rem' }}>
            No exchanges configured yet
          </Typography>
        </Box>
      )}
    </SettingsSectionCard>
  );
};

export default ApiKeysListCard;
