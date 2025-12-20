import React from 'react';
import { Box, Typography, Chip, LinearProgress, Stack } from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import WarningIcon from '@mui/icons-material/Warning';
import ErrorIcon from '@mui/icons-material/Error';

export interface QueueHealthIndicatorProps {
  queueSize: number;
  averageWaitTime?: number; // in minutes
  highPriorityCount?: number;
  thresholds?: {
    good: number;
    warning: number;
    critical: number;
  };
}

export const QueueHealthIndicator: React.FC<QueueHealthIndicatorProps> = ({
  queueSize,
  averageWaitTime = 0,
  highPriorityCount = 0,
  thresholds = { good: 3, warning: 5, critical: 10 }
}) => {

  const getHealthStatus = () => {
    if (queueSize === 0) {
      return {
        label: 'Empty',
        color: 'success' as const,
        icon: <CheckCircleIcon sx={{ fontSize: 18 }} />,
        description: 'No signals in queue',
        severity: 'success' as const
      };
    }

    if (queueSize <= thresholds.good) {
      return {
        label: 'Healthy',
        color: 'success' as const,
        icon: <CheckCircleIcon sx={{ fontSize: 18 }} />,
        description: 'Queue is processing smoothly',
        severity: 'success' as const
      };
    }

    if (queueSize <= thresholds.warning) {
      return {
        label: 'Busy',
        color: 'warning' as const,
        icon: <WarningIcon sx={{ fontSize: 18 }} />,
        description: 'Queue is getting busy',
        severity: 'warning' as const
      };
    }

    return {
      label: 'Critical',
      color: 'error' as const,
      icon: <ErrorIcon sx={{ fontSize: 18 }} />,
      description: 'Queue backlog detected',
      severity: 'error' as const
    };
  };

  const health = getHealthStatus();
  const queueUtilization = Math.min((queueSize / thresholds.critical) * 100, 100);

  const formatWaitTime = (minutes: number) => {
    if (minutes < 60) {
      return `${Math.round(minutes)}m`;
    }
    const hours = Math.floor(minutes / 60);
    const mins = Math.round(minutes % 60);
    return `${hours}h ${mins}m`;
  };

  return (
    <Box
      sx={{
        p: 2,
        bgcolor: 'background.paper',
        borderRadius: 2,
        border: '1px solid',
        borderColor: 'divider',
      }}
    >
      <Stack spacing={2}>
        {/* Header */}
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography variant="subtitle2" fontWeight={600}>
            Queue Health
          </Typography>
          <Chip
            icon={health.icon}
            label={health.label}
            color={health.color}
            size="small"
            sx={{ fontWeight: 600 }}
          />
        </Box>

        {/* Description */}
        <Typography variant="caption" color="text.secondary">
          {health.description}
        </Typography>

        {/* Queue Utilization Bar */}
        <Box>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
            <Typography variant="caption" color="text.secondary">
              Queue Size
            </Typography>
            <Typography variant="caption" fontWeight={600} sx={{ fontFamily: 'monospace' }}>
              {queueSize} / {thresholds.critical}
            </Typography>
          </Box>
          <LinearProgress
            variant="determinate"
            value={queueUtilization}
            color={health.severity}
            sx={{
              height: 6,
              borderRadius: 3,
              bgcolor: 'background.default',
            }}
          />
        </Box>

        {/* Stats Grid */}
        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            gap: 1.5,
            pt: 1,
            borderTop: '1px solid',
            borderColor: 'divider',
          }}
        >
          <Box>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
              Avg Wait
            </Typography>
            <Typography variant="body2" fontWeight={600} sx={{ fontFamily: 'monospace' }}>
              {averageWaitTime > 0 ? formatWaitTime(averageWaitTime) : 'N/A'}
            </Typography>
          </Box>
          <Box>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
              High Priority
            </Typography>
            <Typography variant="body2" fontWeight={600} sx={{ fontFamily: 'monospace' }}>
              {highPriorityCount}
            </Typography>
          </Box>
        </Box>
      </Stack>
    </Box>
  );
};

export default QueueHealthIndicator;
