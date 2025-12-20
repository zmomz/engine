import React from 'react';
import { Card, CardContent, Typography, Box, useTheme } from '@mui/material';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import TrendingDownIcon from '@mui/icons-material/TrendingDown';
import { Line, LineChart, ResponsiveContainer } from 'recharts';
import { safeToFixed, safeNumber } from '../utils/formatters';

export interface MetricCardProps {
  label: string;
  value: string | number;
  change?: number;
  changeLabel?: string;
  trend?: 'up' | 'down' | 'neutral';
  sparklineData?: number[];
  variant?: 'large' | 'small';
  colorScheme?: 'bullish' | 'bearish' | 'neutral' | 'primary';
  icon?: React.ReactNode;
  subtitle?: string;
  loading?: boolean;
}

export const MetricCard: React.FC<MetricCardProps> = ({
  label,
  value,
  change,
  changeLabel,
  trend,
  sparklineData,
  variant = 'large',
  colorScheme = 'neutral',
  icon,
  subtitle,
  loading = false,
}) => {
  const theme = useTheme();

  // Determine color based on color scheme or trend
  const getValueColor = () => {
    if (colorScheme === 'bullish') return theme.palette.bullish.main;
    if (colorScheme === 'bearish') return theme.palette.bearish.main;
    if (colorScheme === 'primary') return theme.palette.primary.main;
    if (trend === 'up') return theme.palette.bullish.main;
    if (trend === 'down') return theme.palette.bearish.main;
    return theme.palette.text.primary;
  };

  const getChangeColor = () => {
    if (!change) return theme.palette.text.secondary;
    return change >= 0 ? theme.palette.bullish.main : theme.palette.bearish.main;
  };

  const getSparklineColor = () => {
    if (colorScheme === 'bullish' || trend === 'up') return theme.palette.bullish.main;
    if (colorScheme === 'bearish' || trend === 'down') return theme.palette.bearish.main;
    return theme.palette.primary.main;
  };

  const formatChange = (val: number) => {
    const num = safeNumber(val);
    const prefix = num >= 0 ? '+' : '';
    return `${prefix}${safeToFixed(num)}%`;
  };

  const valueSize = variant === 'large' ? 'h3' : 'h4';
  const cardPadding = variant === 'large' ? 3 : 2;

  return (
    <Card
      sx={{
        height: '100%',
        transition: 'all 0.3s ease',
        '&:hover': {
          transform: 'translateY(-2px)',
          boxShadow: theme.shadows[4],
        },
      }}
    >
      <CardContent sx={{ p: cardPadding, height: '100%', display: 'flex', flexDirection: 'column' }}>
        {/* Header with label and icon */}
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 1 }}>
          <Typography variant="body2" color="text.secondary" fontWeight={500}>
            {label}
          </Typography>
          {icon && (
            <Box sx={{ color: getValueColor(), opacity: 0.7 }}>
              {icon}
            </Box>
          )}
        </Box>

        {/* Main value */}
        <Typography
          variant={valueSize}
          component="div"
          sx={{
            color: getValueColor(),
            fontWeight: 700,
            fontFamily: typeof value === 'number' ? theme.typography.fontFamilyMonospace : theme.typography.fontFamily,
            mb: 0.5,
            lineHeight: 1.2,
          }}
        >
          {loading ? '—' : value}
        </Typography>

        {/* Subtitle */}
        {subtitle && (
          <Typography variant="caption" color="text.secondary" sx={{ mb: 1 }}>
            {subtitle}
          </Typography>
        )}

        {/* Change indicator */}
        {change !== undefined && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: sparklineData ? 1 : 0 }}>
            {trend === 'up' && <TrendingUpIcon fontSize="small" sx={{ color: getChangeColor() }} />}
            {trend === 'down' && <TrendingDownIcon fontSize="small" sx={{ color: getChangeColor() }} />}
            <Typography
              variant="body2"
              sx={{
                color: getChangeColor(),
                fontWeight: 600,
                fontFamily: theme.typography.fontFamilyMonospace,
              }}
            >
              {formatChange(change)}
            </Typography>
            {changeLabel && (
              <Typography variant="caption" color="text.secondary">
                {changeLabel}
              </Typography>
            )}
          </Box>
        )}

        {/* Sparkline chart */}
        {sparklineData && sparklineData.length > 0 && (
          <Box sx={{ mt: 'auto', height: 40, width: '100%' }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={sparklineData.map((val, idx) => ({ value: val, index: idx }))}>
                <Line
                  type="monotone"
                  dataKey="value"
                  stroke={getSparklineColor()}
                  strokeWidth={2}
                  dot={false}
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </Box>
        )}
      </CardContent>
    </Card>
  );
};

export default MetricCard;
