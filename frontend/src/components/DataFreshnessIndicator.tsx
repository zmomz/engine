import React, { useState, useEffect } from 'react';
import { Box, Typography, Tooltip } from '@mui/material';
import { StatusIndicatorDot } from './AnimatedStatusChip';

interface DataFreshnessIndicatorProps {
  lastUpdated: Date | null;
  warningThresholdSeconds?: number;
  errorThresholdSeconds?: number;
  showText?: boolean;
}

export const DataFreshnessIndicator: React.FC<DataFreshnessIndicatorProps> = ({
  lastUpdated,
  warningThresholdSeconds = 10,
  errorThresholdSeconds = 30,
  showText = true,
}) => {
  const [timeAgo, setTimeAgo] = useState<string>('');
  const [status, setStatus] = useState<'success' | 'warning' | 'error'>('success');

  useEffect(() => {
    const updateTimeAgo = () => {
      if (!lastUpdated) {
        setTimeAgo('Never');
        setStatus('error');
        return;
      }

      const now = new Date();
      const diffSeconds = Math.floor((now.getTime() - lastUpdated.getTime()) / 1000);

      if (diffSeconds < 1) {
        setTimeAgo('Just now');
        setStatus('success');
      } else if (diffSeconds < 60) {
        setTimeAgo(`${diffSeconds}s ago`);
        setStatus(
          diffSeconds > errorThresholdSeconds
            ? 'error'
            : diffSeconds > warningThresholdSeconds
            ? 'warning'
            : 'success'
        );
      } else if (diffSeconds < 3600) {
        const minutes = Math.floor(diffSeconds / 60);
        setTimeAgo(`${minutes}m ago`);
        setStatus('error');
      } else {
        const hours = Math.floor(diffSeconds / 3600);
        setTimeAgo(`${hours}h ago`);
        setStatus('error');
      }
    };

    updateTimeAgo();
    const interval = setInterval(updateTimeAgo, 1000);

    return () => clearInterval(interval);
  }, [lastUpdated, warningThresholdSeconds, errorThresholdSeconds]);

  const tooltipTitle = lastUpdated
    ? `Last updated: ${lastUpdated.toLocaleString()}`
    : 'No data received yet';

  return (
    <Tooltip title={tooltipTitle} arrow>
      <Box
        sx={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 0.5,
          cursor: 'help',
          padding: '2px 8px',
          borderRadius: 1,
          '&:hover': {
            backgroundColor: 'action.hover',
          },
        }}
      >
        <StatusIndicatorDot
          color={status}
          pulsing={status === 'success'}
          size={8}
        />
        {showText && (
          <Typography variant="caption" color="text.secondary">
            {timeAgo}
          </Typography>
        )}
      </Box>
    </Tooltip>
  );
};
