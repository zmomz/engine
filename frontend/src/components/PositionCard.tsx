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
  Tooltip,
} from '@mui/material';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import KeyboardArrowUpIcon from '@mui/icons-material/KeyboardArrowUp';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import TrendingDownIcon from '@mui/icons-material/TrendingDown';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import { PositionGroup } from '../store/positionsStore';
import { safeNumber, safeToFixed, formatCompactCurrency, formatCompactPercent } from '../utils/formatters';

interface PositionCardProps {
  position: PositionGroup;
  onForceClose: (groupId: string) => void;
}

const PositionCard: React.FC<PositionCardProps> = ({ position, onForceClose }) => {
  const [expanded, setExpanded] = useState(false);

  const isProfitable = safeNumber(position.unrealized_pnl_usd) >= 0;
  const pnlColor = isProfitable ? 'success.main' : 'error.main';
  const pyramidProgress = position.max_pyramids > 0
    ? (position.pyramid_count / position.max_pyramids) * 100
    : 0;
  const dcaProgress = position.total_dca_legs > 0
    ? ((position.filled_dca_legs || 0) / position.total_dca_legs) * 100
    : 0;

  // Calculate age
  const getAge = () => {
    if (!position.created_at) return '-';
    const created = new Date(position.created_at);
    const now = new Date();
    const diffMs = now.getTime() - created.getTime();
    const hours = Math.floor(diffMs / (1000 * 60 * 60));
    const days = Math.floor(hours / 24);
    if (days > 0) return `${days}d ${hours % 24}h`;
    return `${hours}h`;
  };

  return (
    <Card
      sx={{
        mb: 2,
        borderLeft: 4,
        borderColor: isProfitable ? 'success.main' : 'error.main',
        bgcolor: 'background.paper',
      }}
    >
      <CardContent sx={{ pb: 1 }}>
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
                label={position.status}
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
              {formatCompactCurrency(position.unrealized_pnl_usd)}
            </Typography>
            <Typography
              variant="caption"
              sx={{ color: pnlColor, display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 0.5 }}
            >
              {isProfitable ? <TrendingUpIcon sx={{ fontSize: 14 }} /> : <TrendingDownIcon sx={{ fontSize: 14 }} />}
              {formatCompactPercent(position.unrealized_pnl_percent)}
            </Typography>
          </Box>
        </Box>

        {/* Quick Stats Row */}
        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1.5 }}>
          <Box>
            <Typography variant="caption" color="text.secondary">Entry</Typography>
            <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.8rem' }}>
              {formatCompactCurrency(position.weighted_avg_entry)}
            </Typography>
          </Box>
          <Box sx={{ textAlign: 'center' }}>
            <Typography variant="caption" color="text.secondary">Invested</Typography>
            <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.8rem' }}>
              {formatCompactCurrency(position.total_invested_usd)}
            </Typography>
          </Box>
          <Box sx={{ textAlign: 'right' }}>
            <Typography variant="caption" color="text.secondary">Age</Typography>
            <Typography variant="body2" sx={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 0.5 }}>
              <AccessTimeIcon sx={{ fontSize: 14 }} />
              {getAge()}
            </Typography>
          </Box>
        </Box>

        {/* Progress Bars */}
        <Box sx={{ mb: 1 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
            <Typography variant="caption" color="text.secondary">
              Pyramids: {position.pyramid_count}/{position.max_pyramids}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              DCA: {position.filled_dca_legs || 0}/{position.total_dca_legs || 0}
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', gap: 1 }}>
            <LinearProgress
              variant="determinate"
              value={pyramidProgress}
              sx={{ flex: 1, height: 4, borderRadius: 2, bgcolor: 'action.hover' }}
            />
            <LinearProgress
              variant="determinate"
              value={dcaProgress}
              sx={{ flex: 1, height: 4, borderRadius: 2, bgcolor: 'action.hover' }}
              color="secondary"
            />
          </Box>
        </Box>

        {/* Expand/Collapse */}
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <IconButton size="small" onClick={() => setExpanded(!expanded)}>
            {expanded ? <KeyboardArrowUpIcon /> : <KeyboardArrowDownIcon />}
          </IconButton>
          <Button
            variant="contained"
            color="error"
            size="small"
            onClick={() => onForceClose(position.id)}
            disabled={position.status === 'CLOSING' || position.status === 'CLOSED'}
            sx={{ fontSize: '0.7rem', py: 0.5 }}
          >
            Force Close
          </Button>
        </Box>
      </CardContent>

      {/* Expanded Details */}
      <Collapse in={expanded}>
        <Divider />
        <CardContent sx={{ bgcolor: 'background.default', pt: 1.5 }}>
          <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1.5 }}>
            <Box>
              <Typography variant="caption" color="text.secondary">Base Entry</Typography>
              <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                {formatCompactCurrency(position.base_entry_price)}
              </Typography>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">TP Mode</Typography>
              <Typography variant="body2">
                {position.tp_mode?.replace('_', ' ').toUpperCase() || '-'}
              </Typography>
            </Box>
            {/* TP Target for aggregate/hybrid/pyramid_aggregate modes */}
            {(position.tp_mode === 'aggregate' || position.tp_mode === 'hybrid' || position.tp_mode === 'pyramid_aggregate') && position.tp_aggregate_percent && (
              <Box sx={{ gridColumn: '1 / -1' }}>
                <Typography variant="caption" color="text.secondary">Aggregate TP Target</Typography>
                <Typography variant="body2" sx={{ fontFamily: 'monospace', color: 'success.main', fontWeight: 600 }}>
                  {position.weighted_avg_entry > 0 ? (
                    <>
                      {formatCompactCurrency(
                        position.side === 'long'
                          ? position.weighted_avg_entry * (1 + position.tp_aggregate_percent / 100)
                          : position.weighted_avg_entry * (1 - position.tp_aggregate_percent / 100)
                      )}
                      <Typography component="span" variant="caption" sx={{ ml: 0.5, color: 'text.secondary' }}>
                        (+{position.tp_aggregate_percent}%)
                      </Typography>
                    </>
                  ) : (
                    `+${position.tp_aggregate_percent}%`
                  )}
                </Typography>
              </Box>
            )}
            <Box>
              <Typography variant="caption" color="text.secondary">Total Quantity</Typography>
              <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                {position.total_filled_quantity ? safeToFixed(position.total_filled_quantity, 4) : '-'}
              </Typography>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">Risk Status</Typography>
              <Typography variant="body2">
                {position.risk_blocked ? '⚠️ Blocked' : position.risk_eligible ? '✅ Eligible' : '○ N/A'}
              </Typography>
            </Box>
            {(safeNumber(position.total_hedged_qty) > 0 || safeNumber(position.total_hedged_value_usd) > 0) && (
              <>
                <Box>
                  <Tooltip title="Cumulative quantity closed to offset losers">
                    <Typography variant="caption" color="text.secondary">
                      Hedged Qty ℹ️
                    </Typography>
                  </Tooltip>
                  <Typography variant="body2" sx={{ fontFamily: 'monospace', color: 'info.main', fontWeight: 500 }}>
                    {safeToFixed(position.total_hedged_qty, 4)}
                  </Typography>
                </Box>
                <Box>
                  <Tooltip title="Cumulative USD value of hedge closes">
                    <Typography variant="caption" color="text.secondary">
                      Hedged Value ℹ️
                    </Typography>
                  </Tooltip>
                  <Typography variant="body2" sx={{ fontFamily: 'monospace', color: 'info.main', fontWeight: 500 }}>
                    ${safeToFixed(position.total_hedged_value_usd, 2)}
                  </Typography>
                </Box>
              </>
            )}
          </Box>

          {/* Risk Timer */}
          {position.risk_timer_expires && (
            <Box sx={{ mt: 1.5, p: 1, bgcolor: 'warning.dark', borderRadius: 1, opacity: 0.9 }}>
              <Typography variant="caption" color="warning.contrastText">
                Risk Timer: {new Date(position.risk_timer_expires).toLocaleTimeString()}
              </Typography>
            </Box>
          )}

        </CardContent>
      </Collapse>
    </Card>
  );
};

export default PositionCard;
