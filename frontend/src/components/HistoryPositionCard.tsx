import React from 'react';
import {
  Card,
  CardContent,
  Box,
  Typography,
  Chip,
} from '@mui/material';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import TrendingDownIcon from '@mui/icons-material/TrendingDown';
import { format } from 'date-fns';
import { PositionGroup } from '../store/positionsStore';
import { safeNumber, formatCompactCurrency, formatCompactPercent } from '../utils/formatters';

interface HistoryPositionCardProps {
  position: PositionGroup;
}

const HistoryPositionCard: React.FC<HistoryPositionCardProps> = ({ position }) => {
  const isProfitable = safeNumber(position.realized_pnl_usd) >= 0;
  const pnlColor = isProfitable ? 'success.main' : 'error.main';

  // Calculate percentage from realized PnL and invested amount
  const pnl = safeNumber(position.realized_pnl_usd);
  const invested = safeNumber(position.total_invested_usd);
  const pnlPercent = invested > 0 ? (pnl / invested) * 100 : 0;

  const formatDuration = () => {
    if (!position.created_at || !position.closed_at) return '-';
    try {
      const start = new Date(position.created_at);
      const end = new Date(position.closed_at);
      const durationMs = end.getTime() - start.getTime();
      const hours = Math.floor(durationMs / (1000 * 60 * 60));
      const days = Math.floor(hours / 24);
      if (days > 0) return `${days}d ${hours % 24}h`;
      const minutes = Math.floor((durationMs % (1000 * 60 * 60)) / (1000 * 60));
      return `${hours}h ${minutes}m`;
    } catch {
      return '-';
    }
  };

  return (
    <Card
      sx={{
        mb: 2,
        borderLeft: 4,
        borderColor: isProfitable ? 'success.main' : 'error.main',
        bgcolor: 'background.paper',
        opacity: 0.9,
      }}
    >
      <CardContent sx={{ pb: '12px !important' }}>
        {/* Header Row */}
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 1 }}>
          <Box>
            <Typography variant="h6" sx={{ fontWeight: 600, fontSize: '1rem' }}>
              {position.symbol}
            </Typography>
            <Box sx={{ display: 'flex', gap: 0.5, mt: 0.5 }}>
              <Chip
                label={position.side.toUpperCase()}
                size="small"
                color={position.side === 'long' ? 'success' : 'error'}
                sx={{ height: 20, fontSize: '0.65rem' }}
              />
              <Chip
                label={position.timeframe || '-'}
                size="small"
                variant="outlined"
                sx={{ height: 20, fontSize: '0.65rem' }}
              />
            </Box>
          </Box>
          <Box sx={{ textAlign: 'right' }}>
            <Typography
              variant="h6"
              sx={{ fontWeight: 700, color: pnlColor, fontSize: '1rem' }}
            >
              {formatCompactCurrency(position.realized_pnl_usd)}
            </Typography>
            <Typography
              variant="caption"
              sx={{ color: pnlColor, display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 0.5 }}
            >
              {isProfitable ? <TrendingUpIcon sx={{ fontSize: 14 }} /> : <TrendingDownIcon sx={{ fontSize: 14 }} />}
              {formatCompactPercent(pnlPercent)}
            </Typography>
          </Box>
        </Box>

        {/* Stats Row */}
        <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
          <Box>
            <Typography variant="caption" color="text.secondary">Entry</Typography>
            <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.8rem' }}>
              {formatCompactCurrency(position.weighted_avg_entry)}
            </Typography>
          </Box>
          <Box sx={{ textAlign: 'center' }}>
            <Typography variant="caption" color="text.secondary">Duration</Typography>
            <Typography variant="body2" sx={{ fontSize: '0.8rem' }}>
              {formatDuration()}
            </Typography>
          </Box>
          <Box sx={{ textAlign: 'right' }}>
            <Typography variant="caption" color="text.secondary">Closed</Typography>
            <Typography variant="body2" sx={{ fontSize: '0.75rem' }}>
              {position.closed_at ? format(new Date(position.closed_at), 'MMM d, HH:mm') : '-'}
            </Typography>
          </Box>
        </Box>
      </CardContent>
    </Card>
  );
};

export default HistoryPositionCard;
