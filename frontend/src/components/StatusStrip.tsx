import React from 'react';
import { Box, Chip, Typography, useTheme } from '@mui/material';
import { StatusIndicatorDot } from './AnimatedStatusChip';

export interface StatusItem {
  label: string;
  status: 'success' | 'error' | 'warning' | 'info';
  value?: string;
  pulsing?: boolean;
}

export interface StatusStripProps {
  items: StatusItem[];
}

export const StatusStrip: React.FC<StatusStripProps> = ({ items }) => {
  const theme = useTheme();

  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        gap: { xs: 2, sm: 3 },
        p: { xs: 1.5, sm: 2 },
        bgcolor: 'background.paper',
        borderRadius: 2,
        mb: 3,
        flexWrap: 'wrap',
        boxShadow: theme.shadows[2],
      }}
    >
      {items.map((item, index) => (
        <Box
          key={index}
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 1,
          }}
        >
          <StatusIndicatorDot color={item.status} pulsing={item.pulsing} size={10} />
          <Typography
            variant="body2"
            sx={{
              fontWeight: 500,
              color: 'text.secondary',
              fontSize: { xs: '0.75rem', sm: '0.875rem' },
            }}
          >
            {item.label}
          </Typography>
          {item.value && (
            <Chip
              label={item.value}
              size="small"
              sx={{
                height: 20,
                fontSize: '0.7rem',
                fontWeight: 600,
              }}
            />
          )}
        </Box>
      ))}
    </Box>
  );
};

export default StatusStrip;
