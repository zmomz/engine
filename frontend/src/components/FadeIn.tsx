import React from 'react';
import { Box, SxProps, Theme } from '@mui/material';

export interface FadeInProps {
  children: React.ReactNode;
  delay?: number;
  duration?: number;
  sx?: SxProps<Theme>;
}

export const FadeIn: React.FC<FadeInProps> = ({
  children,
  delay = 0,
  duration = 0.5,
  sx = {}
}) => {
  return (
    <Box
      sx={{
        animation: `fadeIn ${duration}s ease-in ${delay}s both`,
        '@keyframes fadeIn': {
          '0%': {
            opacity: 0,
            transform: 'translateY(10px)',
          },
          '100%': {
            opacity: 1,
            transform: 'translateY(0)',
          },
        },
        ...sx
      }}
    >
      {children}
    </Box>
  );
};

export default FadeIn;
