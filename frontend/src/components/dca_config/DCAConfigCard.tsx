import React, { useState } from 'react';
import {
  Card,
  CardContent,
  Box,
  Typography,
  Chip,
  IconButton,
  Collapse,
  Divider,
} from '@mui/material';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import KeyboardArrowUpIcon from '@mui/icons-material/KeyboardArrowUp';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import { DCAConfiguration } from '../../api/dcaConfig';

interface DCAConfigCardProps {
  config: DCAConfiguration;
  onEdit: (config: DCAConfiguration) => void;
  onDelete: (id: string) => void;
}

const DCAConfigCard: React.FC<DCAConfigCardProps> = ({ config, onEdit, onDelete }) => {
  const [expanded, setExpanded] = useState(false);

  const getEntryColor = () => {
    return config.entry_order_type === 'market' ? 'warning' : 'default';
  };

  const getTpModeLabel = () => {
    switch (config.tp_mode) {
      case 'per_leg': return 'Per Leg';
      case 'aggregate': return 'Aggregate';
      case 'hybrid': return 'Hybrid';
      case 'pyramid_aggregate': return 'Pyr Agg';
      default: return config.tp_mode;
    }
  };

  return (
    <Card
      sx={{
        mb: 1.5,
        borderLeft: 3,
        borderColor: 'primary.main',
        bgcolor: 'background.paper',
      }}
    >
      <CardContent sx={{ py: 1.5, px: 2, '&:last-child': { pb: 1.5 } }}>
        {/* Header Row */}
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <Box sx={{ flex: 1, minWidth: 0 }}>
            <Typography variant="subtitle1" sx={{ fontWeight: 600, fontSize: '0.95rem' }}>
              {config.pair}
            </Typography>
            <Box sx={{ display: 'flex', gap: 0.5, mt: 0.5, flexWrap: 'wrap' }}>
              <Chip
                label={config.entry_order_type === 'market' ? 'Market' : 'Limit'}
                size="small"
                color={getEntryColor()}
                sx={{ height: 20, fontSize: '0.65rem' }}
              />
              <Chip
                label={`${config.timeframe}m`}
                size="small"
                variant="outlined"
                sx={{ height: 20, fontSize: '0.65rem' }}
              />
              <Chip
                label={getTpModeLabel()}
                size="small"
                variant="outlined"
                sx={{ height: 20, fontSize: '0.65rem' }}
              />
            </Box>
          </Box>

          {/* Actions */}
          <Box sx={{ display: 'flex', gap: 0.5, ml: 1 }}>
            <IconButton size="small" onClick={() => onEdit(config)} sx={{ p: 0.5 }}>
              <EditIcon sx={{ fontSize: 18 }} />
            </IconButton>
            <IconButton size="small" color="error" onClick={() => onDelete(config.id)} sx={{ p: 0.5 }}>
              <DeleteIcon sx={{ fontSize: 18 }} />
            </IconButton>
            <IconButton size="small" onClick={() => setExpanded(!expanded)} sx={{ p: 0.5 }}>
              {expanded ? <KeyboardArrowUpIcon sx={{ fontSize: 18 }} /> : <KeyboardArrowDownIcon sx={{ fontSize: 18 }} />}
            </IconButton>
          </Box>
        </Box>

        {/* Quick Stats Row */}
        <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 1.5, gap: 2 }}>
          <Box>
            <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.65rem' }}>
              Max Pyramids
            </Typography>
            <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.85rem', fontWeight: 600 }}>
              {config.max_pyramids}
            </Typography>
          </Box>
          <Box>
            <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.65rem' }}>
              DCA Levels
            </Typography>
            <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.85rem', fontWeight: 600 }}>
              {config.dca_levels?.length || 0}
            </Typography>
          </Box>
          <Box>
            <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.65rem' }}>
              Exchange
            </Typography>
            <Typography variant="body2" sx={{ fontSize: '0.85rem' }}>
              {config.exchange}
            </Typography>
          </Box>
        </Box>
      </CardContent>

      {/* Expanded Details */}
      <Collapse in={expanded}>
        <Divider />
        <CardContent sx={{ bgcolor: 'background.default', py: 1.5, px: 2 }}>
          {/* DCA Levels Summary */}
          {config.dca_levels && config.dca_levels.length > 0 && (
            <Box sx={{ mb: 1.5 }}>
              <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.7rem', fontWeight: 600 }}>
                DCA Levels
              </Typography>
              <Box sx={{ mt: 0.5 }}>
                {config.dca_levels.map((level, idx) => (
                  <Box
                    key={idx}
                    sx={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      py: 0.25,
                      borderBottom: idx < config.dca_levels.length - 1 ? '1px solid' : 'none',
                      borderColor: 'divider',
                    }}
                  >
                    <Typography variant="caption" sx={{ fontSize: '0.7rem' }}>
                      #{idx}: Gap {level.gap_percent}%
                    </Typography>
                    <Typography variant="caption" sx={{ fontSize: '0.7rem', fontFamily: 'monospace' }}>
                      {level.weight_percent}% @ {level.tp_percent}% TP
                    </Typography>
                  </Box>
                ))}
              </Box>
            </Box>
          )}

          {/* TP Settings */}
          {config.tp_settings?.tp_aggregate_percent !== undefined && config.tp_settings.tp_aggregate_percent > 0 && (
            <Box>
              <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.7rem' }}>
                Aggregate TP: {config.tp_settings.tp_aggregate_percent}%
              </Typography>
            </Box>
          )}

          {/* Per-Pyramid TP Overrides */}
          {config.tp_mode === 'pyramid_aggregate' && config.tp_settings?.pyramid_tp_percents && Object.keys(config.tp_settings.pyramid_tp_percents).length > 0 && (
            <Box sx={{ mt: 0.5 }}>
              <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.7rem' }}>
                Pyramid TPs: {Object.entries(config.tp_settings.pyramid_tp_percents).map(([idx, tp]) => `P${idx}: ${tp}%`).join(', ')}
              </Typography>
            </Box>
          )}

          {/* Pyramid Overrides */}
          {config.pyramid_specific_levels && Object.keys(config.pyramid_specific_levels).length > 0 && (
            <Box sx={{ mt: 1 }}>
              <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.7rem' }}>
                Custom pyramids: {Object.keys(config.pyramid_specific_levels).join(', ')}
              </Typography>
            </Box>
          )}
        </CardContent>
      </Collapse>
    </Card>
  );
};

export default DCAConfigCard;
