import React, { useState } from 'react';
import {
  Card,
  CardContent,
  Box,
  Typography,
  Chip,
  IconButton,
  Collapse,
  Button,
  Divider,
  LinearProgress,
} from '@mui/material';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import KeyboardArrowUpIcon from '@mui/icons-material/KeyboardArrowUp';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import TrendingDownIcon from '@mui/icons-material/TrendingDown';
import { format } from 'date-fns';
import { safeToFixed, safeNumber } from '../utils/formatters';

interface QueueSignal {
  id: string;
  symbol: string;
  side: string;
  timeframe: number | string;
  exchange: string;
  priority_score: number;
  priority_explanation?: string | null;
  current_loss_percent?: number | null;
  replacement_count?: number | null;
  queued_at: string;
  status?: string;
}

interface QueueSignalCardProps {
  signal: QueueSignal;
  onPromote: (signalId: string) => void;
  onRemove: (signalId: string) => void;
}

const QueueSignalCard: React.FC<QueueSignalCardProps> = ({ signal, onPromote, onRemove }) => {
  const [expanded, setExpanded] = useState(false);

  const getPriorityColor = (score: number) => {
    if (score >= 80) return '#ef4444'; // Red - Very High
    if (score >= 60) return '#f59e0b'; // Amber - High
    if (score >= 40) return '#3b82f6'; // Blue - Medium
    return '#6b7280'; // Gray - Low
  };

  const getPriorityLabel = (score: number) => {
    if (score >= 80) return 'CRITICAL';
    if (score >= 60) return 'HIGH';
    if (score >= 40) return 'MEDIUM';
    return 'LOW';
  };

  const formatPercentage = (value: number | null | undefined) => {
    if (value === null || value === undefined) return '-';
    const num = safeNumber(value);
    return `${num >= 0 ? '+' : ''}${safeToFixed(num)}%`;
  };

  const getTimeInQueue = () => {
    try {
      const queuedTime = new Date(signal.queued_at);
      const now = new Date();
      const diffMs = now.getTime() - queuedTime.getTime();
      const minutes = Math.floor(diffMs / (1000 * 60));
      const hours = Math.floor(minutes / 60);
      if (hours > 0) return `${hours}h ${minutes % 60}m`;
      return `${minutes}m`;
    } catch {
      return '-';
    }
  };

  const priorityColor = getPriorityColor(signal.priority_score || 0);
  const hasLoss = (signal.current_loss_percent || 0) < 0;

  return (
    <Card
      sx={{
        mb: 2,
        borderLeft: 4,
        borderColor: priorityColor,
        bgcolor: 'background.paper',
        position: 'relative',
        overflow: 'visible',
      }}
    >
      {/* Priority Badge */}
      <Box
        sx={{
          position: 'absolute',
          top: -8,
          right: 12,
          bgcolor: priorityColor,
          color: 'white',
          px: 1,
          py: 0.25,
          borderRadius: 1,
          fontSize: '0.6rem',
          fontWeight: 700,
          boxShadow: `0 2px 8px ${priorityColor}60`,
        }}
      >
        {getPriorityLabel(signal.priority_score || 0)}
      </Box>

      <CardContent sx={{ pb: 1, pt: 2 }}>
        {/* Header Row */}
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 1.5 }}>
          <Box>
            <Typography variant="h6" sx={{ fontWeight: 600, fontSize: '1rem' }}>
              {signal.symbol}
            </Typography>
            <Box sx={{ display: 'flex', gap: 0.5, mt: 0.5 }}>
              <Chip
                label={signal.side.toUpperCase()}
                size="small"
                color={signal.side === 'long' ? 'success' : 'error'}
                sx={{ height: 20, fontSize: '0.65rem' }}
              />
              <Chip
                label={signal.timeframe}
                size="small"
                variant="outlined"
                sx={{ height: 20, fontSize: '0.65rem' }}
              />
            </Box>
          </Box>
          <Box sx={{ textAlign: 'right' }}>
            <Typography
              variant="h5"
              sx={{
                fontWeight: 700,
                color: priorityColor,
                fontFamily: 'monospace',
              }}
            >
              {safeToFixed(signal.priority_score, 0)}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              Priority Score
            </Typography>
          </Box>
        </Box>

        {/* Priority Progress Bar */}
        <Box sx={{ mb: 1.5 }}>
          <LinearProgress
            variant="determinate"
            value={signal.priority_score || 0}
            sx={{
              height: 6,
              borderRadius: 3,
              bgcolor: 'action.hover',
              '& .MuiLinearProgress-bar': {
                bgcolor: priorityColor,
                borderRadius: 3,
              },
            }}
          />
        </Box>

        {/* Quick Stats Row */}
        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
          <Box>
            <Typography variant="caption" color="text.secondary">Current Loss</Typography>
            <Typography
              variant="body2"
              sx={{
                fontFamily: 'monospace',
                fontSize: '0.85rem',
                color: hasLoss ? 'error.main' : 'text.primary',
                display: 'flex',
                alignItems: 'center',
                gap: 0.5,
              }}
            >
              {hasLoss && <TrendingDownIcon sx={{ fontSize: 14 }} />}
              {formatPercentage(signal.current_loss_percent)}
            </Typography>
          </Box>
          <Box sx={{ textAlign: 'center' }}>
            <Typography variant="caption" color="text.secondary">Replacements</Typography>
            <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.85rem' }}>
              {signal.replacement_count || 0}
            </Typography>
          </Box>
          <Box sx={{ textAlign: 'right' }}>
            <Typography variant="caption" color="text.secondary">In Queue</Typography>
            <Typography
              variant="body2"
              sx={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 0.5, fontSize: '0.85rem' }}
            >
              <AccessTimeIcon sx={{ fontSize: 14 }} />
              {getTimeInQueue()}
            </Typography>
          </Box>
        </Box>

        {/* Action Buttons */}
        <Box sx={{ display: 'flex', gap: 1, mt: 1 }}>
          <Button
            variant="contained"
            color="primary"
            size="small"
            onClick={() => onPromote(signal.id)}
            sx={{ fontSize: '0.7rem', py: 0.5, flex: 1 }}
          >
            Promote
          </Button>
          <Button
            variant="outlined"
            color="error"
            size="small"
            onClick={() => onRemove(signal.id)}
            sx={{ fontSize: '0.7rem', py: 0.5, flex: 1 }}
          >
            Remove
          </Button>
          <IconButton size="small" onClick={() => setExpanded(!expanded)}>
            {expanded ? <KeyboardArrowUpIcon /> : <KeyboardArrowDownIcon />}
          </IconButton>
        </Box>
      </CardContent>

      {/* Expanded Details */}
      <Collapse in={expanded}>
        <Divider />
        <CardContent sx={{ bgcolor: 'background.default', pt: 1.5 }}>
          <Box sx={{ mb: 1.5 }}>
            <Typography variant="caption" color="text.secondary">Priority Reason</Typography>
            <Typography variant="body2" sx={{ mt: 0.5 }}>
              {signal.priority_explanation || 'No explanation available'}
            </Typography>
          </Box>

          <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1.5 }}>
            <Box>
              <Typography variant="caption" color="text.secondary">Exchange</Typography>
              <Typography variant="body2">{signal.exchange}</Typography>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">Queued At</Typography>
              <Typography variant="body2" sx={{ fontSize: '0.8rem' }}>
                {signal.queued_at ? format(new Date(signal.queued_at), 'HH:mm:ss') : '-'}
              </Typography>
            </Box>
          </Box>
        </CardContent>
      </Collapse>
    </Card>
  );
};

export default QueueSignalCard;
