import React from 'react';
import { Box, CircularProgress, useTheme, useMediaQuery } from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';

interface PullToRefreshIndicatorProps {
  pullDistance: number;
  isRefreshing: boolean;
  threshold?: number;
}

const PullToRefreshIndicator: React.FC<PullToRefreshIndicatorProps> = ({
  pullDistance,
  isRefreshing,
  threshold = 80,
}) => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

  // Only show on mobile
  if (!isMobile) return null;

  // Don't show if not pulling and not refreshing
  if (pullDistance === 0 && !isRefreshing) return null;

  const progress = Math.min((pullDistance / threshold) * 100, 100);
  const rotation = (pullDistance / threshold) * 360;

  return (
    <Box
      sx={{
        position: 'fixed',
        top: 64, // Below header
        left: '50%',
        transform: 'translateX(-50%)',
        zIndex: theme.zIndex.appBar + 2,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        transition: isRefreshing ? 'none' : 'opacity 0.2s',
        opacity: pullDistance > 10 || isRefreshing ? 1 : 0,
      }}
    >
      <Box
        sx={{
          bgcolor: 'background.paper',
          borderRadius: '50%',
          p: 1,
          boxShadow: theme.shadows[4],
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        {isRefreshing ? (
          <CircularProgress size={24} thickness={4} />
        ) : (
          <RefreshIcon
            sx={{
              fontSize: 24,
              color: progress >= 100 ? 'primary.main' : 'text.secondary',
              transform: `rotate(${rotation}deg)`,
              transition: 'transform 0.1s linear',
            }}
          />
        )}
      </Box>
    </Box>
  );
};

export default PullToRefreshIndicator;
