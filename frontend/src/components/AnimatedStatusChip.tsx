import React from 'react';
import { Chip, ChipProps, Box, keyframes } from '@mui/material';

const pulse = keyframes`
  0% {
    box-shadow: 0 0 0 0 currentColor;
  }
  50% {
    box-shadow: 0 0 0 4px transparent;
  }
  100% {
    box-shadow: 0 0 0 0 transparent;
  }
`;

const fadeIn = keyframes`
  from {
    opacity: 0;
    transform: scale(0.9);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
`;

interface AnimatedStatusChipProps extends Omit<ChipProps, 'color'> {
  color?: ChipProps['color'];
  animated?: boolean;
  pulsing?: boolean;
}

export const AnimatedStatusChip: React.FC<AnimatedStatusChipProps> = ({
  animated = true,
  pulsing = false,
  sx,
  ...props
}) => {
  return (
    <Chip
      {...props}
      sx={{
        animation: animated ? `${fadeIn} 0.3s ease-in-out` : undefined,
        position: 'relative',
        '&::before': pulsing
          ? {
              content: '""',
              position: 'absolute',
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              borderRadius: 'inherit',
              animation: `${pulse} 2s ease-in-out infinite`,
              opacity: 0.6,
            }
          : undefined,
        transition: 'all 0.3s ease-in-out',
        '&:hover': {
          transform: 'scale(1.05)',
        },
        ...sx,
      }}
    />
  );
};

interface StatusIndicatorDotProps {
  color: 'success' | 'error' | 'warning' | 'info';
  pulsing?: boolean;
  size?: number;
}

export const StatusIndicatorDot: React.FC<StatusIndicatorDotProps> = ({
  color,
  pulsing = false,
  size = 8,
}) => {
  const colorMap = {
    success: '#4caf50',
    error: '#f44336',
    warning: '#ff9800',
    info: '#2196f3',
  };

  return (
    <Box
      sx={{
        width: size,
        height: size,
        borderRadius: '50%',
        backgroundColor: colorMap[color],
        display: 'inline-block',
        animation: pulsing ? `${pulse} 2s ease-in-out infinite` : undefined,
        boxShadow: `0 0 0 0 ${colorMap[color]}`,
      }}
    />
  );
};
