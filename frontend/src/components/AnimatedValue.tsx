import React, { useState, useEffect, useRef } from 'react';
import { Box, Typography, keyframes } from '@mui/material';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import TrendingDownIcon from '@mui/icons-material/TrendingDown';
import { safeToFixed } from '../utils/formatters';

const flashGreen = keyframes`
  0%, 100% {
    background-color: transparent;
  }
  50% {
    background-color: rgba(76, 175, 80, 0.2);
  }
`;

const flashRed = keyframes`
  0%, 100% {
    background-color: transparent;
  }
  50% {
    background-color: rgba(244, 67, 54, 0.2);
  }
`;

interface AnimatedValueProps {
  value: number;
  format?: (value: number) => string;
  variant?: 'h1' | 'h2' | 'h3' | 'h4' | 'h5' | 'h6' | 'body1' | 'body2';
  showTrend?: boolean;
  colorize?: boolean;
  duration?: number;
}

export const AnimatedValue: React.FC<AnimatedValueProps> = ({
  value,
  format = (v) => safeToFixed(v),
  variant = 'h4',
  showTrend = false,
  colorize = true,
  duration = 300,
}) => {
  const [displayValue, setDisplayValue] = useState(value);
  const [isAnimating, setIsAnimating] = useState(false);
  const [trend, setTrend] = useState<'up' | 'down' | null>(null);
  const previousValue = useRef(value);
  const animationFrame = useRef<number | undefined>(undefined);

  useEffect(() => {
    if (previousValue.current === value) return;

    setIsAnimating(true);
    const isIncreasing = value > previousValue.current;
    setTrend(isIncreasing ? 'up' : 'down');

    const startValue = previousValue.current;
    const endValue = value;
    const startTime = Date.now();

    const animate = () => {
      const now = Date.now();
      const progress = Math.min((now - startTime) / duration, 1);

      // Easing function (ease-out)
      const easeOutQuad = (t: number) => t * (2 - t);
      const easedProgress = easeOutQuad(progress);

      const currentValue = startValue + (endValue - startValue) * easedProgress;
      setDisplayValue(currentValue);

      if (progress < 1) {
        animationFrame.current = requestAnimationFrame(animate);
      } else {
        setDisplayValue(endValue);
        setIsAnimating(false);
        setTimeout(() => setTrend(null), 1000);
      }
    };

    animationFrame.current = requestAnimationFrame(animate);
    previousValue.current = value;

    return () => {
      if (animationFrame.current) {
        cancelAnimationFrame(animationFrame.current);
      }
    };
  }, [value, duration]);

  const getColor = () => {
    if (!colorize) return 'text.primary';
    return displayValue >= 0 ? 'success.main' : 'error.main';
  };

  const getAnimation = () => {
    if (!isAnimating || !colorize) return undefined;
    return trend === 'up' ? `${flashGreen} 0.5s ease-in-out` : `${flashRed} 0.5s ease-in-out`;
  };

  return (
    <Box
      sx={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 0.5,
        padding: '2px 8px',
        borderRadius: 1,
        animation: getAnimation(),
        transition: 'color 0.3s ease-in-out',
      }}
    >
      <Typography variant={variant} color={getColor()} sx={{ fontWeight: 'inherit' }}>
        {format(displayValue)}
      </Typography>
      {showTrend && trend && (
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            animation: 'fadeIn 0.3s ease-in-out',
            '@keyframes fadeIn': {
              from: { opacity: 0, transform: 'scale(0.8)' },
              to: { opacity: 1, transform: 'scale(1)' },
            },
          }}
        >
          {trend === 'up' ? (
            <TrendingUpIcon color="success" fontSize="small" />
          ) : (
            <TrendingDownIcon color="error" fontSize="small" />
          )}
        </Box>
      )}
    </Box>
  );
};

interface AnimatedCurrencyProps {
  value: number;
  variant?: 'h1' | 'h2' | 'h3' | 'h4' | 'h5' | 'h6' | 'body1' | 'body2';
  showTrend?: boolean;
  colorize?: boolean;
}

export const AnimatedCurrency: React.FC<AnimatedCurrencyProps> = ({
  value,
  variant = 'h4',
  showTrend = false,
  colorize = true,
}) => {
  const formatCurrency = (val: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(val);
  };

  return (
    <AnimatedValue
      value={value}
      format={formatCurrency}
      variant={variant}
      showTrend={showTrend}
      colorize={colorize}
    />
  );
};

interface AnimatedPercentageProps {
  value: number;
  variant?: 'h1' | 'h2' | 'h3' | 'h4' | 'h5' | 'h6' | 'body1' | 'body2';
  showTrend?: boolean;
  colorize?: boolean;
}

export const AnimatedPercentage: React.FC<AnimatedPercentageProps> = ({
  value,
  variant = 'h4',
  showTrend = false,
  colorize = true,
}) => {
  const formatPercentage = (val: number) => `${safeToFixed(val)}%`;

  return (
    <AnimatedValue
      value={value}
      format={formatPercentage}
      variant={variant}
      showTrend={showTrend}
      colorize={colorize}
    />
  );
};
