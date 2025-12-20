import React from 'react';
import { Box, Typography, Chip, useTheme, Paper } from '@mui/material';
import { format } from 'date-fns';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import InfoIcon from '@mui/icons-material/Info';

export interface TimelineItem {
  id: string;
  timestamp?: string | Date | null;
  title: string;
  description?: string;
  type?: 'success' | 'error' | 'info' | 'warning';
  metadata?: Record<string, any>;
}

export interface TimelineProps {
  items: TimelineItem[];
  maxItems?: number;
  compact?: boolean;
}

export const Timeline: React.FC<TimelineProps> = ({
  items,
  maxItems = 10,
  compact = false
}) => {
  const theme = useTheme();

  const getIcon = (type?: string) => {
    switch (type) {
      case 'success':
        return <CheckCircleIcon sx={{ fontSize: 20, color: 'success.main' }} />;
      case 'error':
        return <ErrorIcon sx={{ fontSize: 20, color: 'error.main' }} />;
      case 'warning':
        return <InfoIcon sx={{ fontSize: 20, color: 'warning.main' }} />;
      default:
        return <InfoIcon sx={{ fontSize: 20, color: 'info.main' }} />;
    }
  };

  const getColor = (type?: string) => {
    switch (type) {
      case 'success':
        return theme.palette.success.main;
      case 'error':
        return theme.palette.error.main;
      case 'warning':
        return theme.palette.warning.main;
      default:
        return theme.palette.info.main;
    }
  };

  const formatTimestamp = (timestamp?: string | Date | null) => {
    if (!timestamp) {
      return 'Unknown time';
    }
    try {
      const date = typeof timestamp === 'string' ? new Date(timestamp) : timestamp;
      return format(date, 'MMM d, h:mm a');
    } catch {
      return 'Unknown time';
    }
  };

  const displayItems = items.slice(0, maxItems);

  if (displayItems.length === 0) {
    return (
      <Box sx={{ p: 3, textAlign: 'center' }}>
        <Typography variant="body2" color="text.secondary">
          No timeline items to display
        </Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ position: 'relative', pl: compact ? 2 : 3 }}>
      {/* Vertical line */}
      <Box
        sx={{
          position: 'absolute',
          left: compact ? 7 : 11,
          top: 0,
          bottom: 0,
          width: 2,
          bgcolor: 'divider',
        }}
      />

      {displayItems.map((item, index) => (
        <Box
          key={item.id}
          sx={{
            position: 'relative',
            pb: index === displayItems.length - 1 ? 0 : compact ? 2 : 3,
          }}
        >
          {/* Icon/dot */}
          <Box
            sx={{
              position: 'absolute',
              left: compact ? -16 : -24,
              top: 4,
              width: compact ? 24 : 32,
              height: compact ? 24 : 32,
              borderRadius: '50%',
              bgcolor: 'background.paper',
              border: `2px solid ${getColor(item.type)}`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              zIndex: 1,
            }}
          >
            {getIcon(item.type)}
          </Box>

          {/* Content */}
          <Paper
            variant="outlined"
            sx={{
              p: compact ? 1.5 : 2,
              ml: compact ? 1 : 2,
              '&:hover': {
                bgcolor: 'action.hover',
              },
              transition: 'background-color 0.2s',
            }}
          >
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 0.5 }}>
              <Typography
                variant={compact ? 'body2' : 'body1'}
                fontWeight={600}
                sx={{ flex: 1 }}
              >
                {item.title}
              </Typography>
              <Typography
                variant="caption"
                color="text.secondary"
                sx={{ ml: 2, whiteSpace: 'nowrap' }}
              >
                {formatTimestamp(item.timestamp)}
              </Typography>
            </Box>

            {item.description && (
              <Typography
                variant={compact ? 'caption' : 'body2'}
                color="text.secondary"
                sx={{ mb: item.metadata ? 1 : 0 }}
              >
                {item.description}
              </Typography>
            )}

            {item.metadata && Object.keys(item.metadata).length > 0 && (
              <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mt: 1 }}>
                {Object.entries(item.metadata).map(([key, value]) => (
                  <Chip
                    key={key}
                    label={`${key}: ${value}`}
                    size="small"
                    variant="outlined"
                    sx={{ height: 20, fontSize: '0.7rem' }}
                  />
                ))}
              </Box>
            )}
          </Paper>
        </Box>
      ))}
    </Box>
  );
};

export default Timeline;
