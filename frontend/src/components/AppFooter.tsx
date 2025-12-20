import React from 'react';
import { Box, Typography, Chip, useTheme } from '@mui/material';
import InfoIcon from '@mui/icons-material/Info';

export interface AppFooterProps {
  compact?: boolean;
}

export const AppFooter: React.FC<AppFooterProps> = ({ compact = false }) => {
  const theme = useTheme();
  const version = '1.0.0';
  const buildDate = '2025-12-18';

  if (compact) {
    return (
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          py: 1,
          px: 2,
          borderTop: `1px solid ${theme.palette.divider}`,
          mt: 'auto',
        }}
      >
        <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.7rem' }}>
          Trading Engine v{version}
        </Typography>
      </Box>
    );
  }

  return (
    <Box
      sx={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        py: 2,
        px: 3,
        borderTop: `1px solid ${theme.palette.divider}`,
        mt: 'auto',
        flexWrap: 'wrap',
        gap: 2,
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <InfoIcon sx={{ fontSize: 16, color: 'text.secondary' }} />
        <Typography variant="caption" color="text.secondary">
          Trading Engine Dashboard v{version}
        </Typography>
        <Chip
          label={`Build ${buildDate}`}
          size="small"
          variant="outlined"
          sx={{ height: 20, fontSize: '0.65rem' }}
        />
      </Box>

      <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
        <Chip
          label="Dark Mode"
          size="small"
          color="primary"
          variant="outlined"
          sx={{ height: 20, fontSize: '0.65rem' }}
        />
        <Chip
          label="Real-time Updates"
          size="small"
          color="success"
          variant="outlined"
          sx={{ height: 20, fontSize: '0.65rem' }}
        />
      </Box>
    </Box>
  );
};

export default AppFooter;
