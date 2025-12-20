import React from 'react';
import { Box, Typography, useTheme } from '@mui/material';

export interface ProgressBarProps {
  value: number;
  max?: number;
  variant?: 'determinate' | 'indeterminate';
  colorScheme?: 'success' | 'warning' | 'error' | 'info' | 'bullish' | 'bearish' | 'primary';
  showLabel?: boolean;
  label?: string;
  height?: number;
  animate?: boolean;
}

export const ProgressBar: React.FC<ProgressBarProps> = ({
  value,
  max = 100,
  variant = 'determinate',
  colorScheme = 'primary',
  showLabel = true,
  label,
  height = 8,
  animate = true,
}) => {
  const theme = useTheme();
  const percentage = Math.min((value / max) * 100, 100);

  const getColor = () => {
    switch (colorScheme) {
      case 'success':
      case 'bullish':
        return theme.palette.bullish.main;
      case 'error':
      case 'bearish':
        return theme.palette.bearish.main;
      case 'warning':
        return theme.palette.warning.main;
      case 'info':
        return theme.palette.info.main;
      case 'primary':
      default:
        return theme.palette.primary.main;
    }
  };

  const getBackgroundColor = () => {
    const color = getColor();
    return theme.palette.mode === 'dark'
      ? `${color}20`
      : `${color}15`;
  };

  return (
    <Box sx={{ width: '100%' }}>
      {showLabel && (
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.5 }}>
          {label && (
            <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.75rem' }}>
              {label}
            </Typography>
          )}
          <Typography
            variant="body2"
            sx={{
              fontWeight: 600,
              fontSize: '0.75rem',
              color: getColor(),
            }}
          >
            {Math.round(percentage)}%
          </Typography>
        </Box>
      )}
      <Box
        sx={{
          width: '100%',
          height,
          bgcolor: getBackgroundColor(),
          borderRadius: height / 2,
          overflow: 'hidden',
          position: 'relative',
        }}
      >
        <Box
          sx={{
            width: variant === 'determinate' ? `${percentage}%` : '100%',
            height: '100%',
            bgcolor: getColor(),
            borderRadius: height / 2,
            transition: animate ? 'width 0.3s ease-in-out' : 'none',
            ...(variant === 'indeterminate' && {
              animation: 'indeterminateAnimation 1.5s ease-in-out infinite',
              '@keyframes indeterminateAnimation': {
                '0%': {
                  transform: 'translateX(-100%)',
                },
                '50%': {
                  transform: 'translateX(0%)',
                },
                '100%': {
                  transform: 'translateX(100%)',
                },
              },
            }),
          }}
        />
      </Box>
    </Box>
  );
};

export interface RiskGaugeProps {
  value: number;
  max?: number;
  thresholds?: {
    low: number;
    medium: number;
    high: number;
  };
  label?: string;
  showValue?: boolean;
}

export const RiskGauge: React.FC<RiskGaugeProps> = ({
  value,
  max = 100,
  thresholds = { low: 30, medium: 60, high: 100 },
  label,
  showValue = true,
}) => {
  const percentage = (value / max) * 100;

  const getColorScheme = (): 'success' | 'warning' | 'error' => {
    if (percentage <= thresholds.low) return 'success';
    if (percentage <= thresholds.medium) return 'warning';
    return 'error';
  };

  const getRiskLevel = () => {
    if (percentage <= thresholds.low) return 'Low';
    if (percentage <= thresholds.medium) return 'Medium';
    return 'High';
  };

  return (
    <Box>
      {label && (
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
          <Typography variant="body2" color="text.secondary">
            {label}
          </Typography>
          {showValue && (
            <Typography variant="body2" sx={{ fontWeight: 600 }}>
              {getRiskLevel()} ({Math.round(percentage)}%)
            </Typography>
          )}
        </Box>
      )}
      <ProgressBar
        value={value}
        max={max}
        colorScheme={getColorScheme()}
        showLabel={false}
        height={12}
      />
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 0.5 }}>
        <Typography variant="caption" color="success.main">
          Low
        </Typography>
        <Typography variant="caption" color="warning.main">
          Medium
        </Typography>
        <Typography variant="caption" color="error.main">
          High
        </Typography>
      </Box>
    </Box>
  );
};

export default ProgressBar;
