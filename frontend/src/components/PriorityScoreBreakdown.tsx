import React, { useState } from 'react';
import { Box, Typography, Popover, Chip, LinearProgress, Stack } from '@mui/material';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import TrendingDownIcon from '@mui/icons-material/TrendingDown';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import RepeatIcon from '@mui/icons-material/Repeat';
import { safeToFixed, safeNumber } from '../utils/formatters';

export interface PriorityScoreBreakdownProps {
  score: number;
  explanation: string | null;
  currentLoss?: number | null;
  replacementCount?: number;
  queuedAt?: string;
}

export const PriorityScoreBreakdown: React.FC<PriorityScoreBreakdownProps> = ({
  score,
  explanation,
  currentLoss,
  replacementCount,
  queuedAt
}) => {
  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null);

  const handlePopoverOpen = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handlePopoverClose = () => {
    setAnchorEl(null);
  };

  const open = Boolean(anchorEl);

  // Determine score tier and color based on backend priority tiers
  // Tier 0: 10M+ (pyramid), Tier 1: 1M+ (deep loss), Tier 2: 10K+ (replacements), Tier 3: 1K+ (FIFO)
  const getScoreTier = (score: number) => {
    if (score >= 1_000_000) return { label: 'Critical', color: 'error' as const, bgColor: '#ef444420' };
    if (score >= 10_000) return { label: 'High', color: 'warning' as const, bgColor: '#f59e0b20' };
    if (score >= 1_000) return { label: 'Medium', color: 'info' as const, bgColor: '#3b82f620' };
    return { label: 'Low', color: 'default' as const, bgColor: '#6b728020' };
  };

  const tier = getScoreTier(score);

  // Parse explanation to extract contributing factors
  const getFactors = () => {
    const factors = [];

    if (currentLoss && currentLoss < 0) {
      factors.push({
        icon: <TrendingDownIcon sx={{ fontSize: 16 }} />,
        label: 'Loss Depth',
        value: `${safeToFixed(Math.abs(safeNumber(currentLoss)))}%`,
        description: 'Deeper losses increase priority'
      });
    }

    if (replacementCount && replacementCount > 0) {
      factors.push({
        icon: <RepeatIcon sx={{ fontSize: 16 }} />,
        label: 'Replacements',
        value: replacementCount.toString(),
        description: 'Multiple replacements increase priority'
      });
    }

    if (queuedAt) {
      try {
        const queueTime = new Date(queuedAt);
        const now = new Date();
        const hoursInQueue = Math.floor((now.getTime() - queueTime.getTime()) / (1000 * 60 * 60));
        if (hoursInQueue > 0) {
          factors.push({
            icon: <AccessTimeIcon sx={{ fontSize: 16 }} />,
            label: 'Wait Time',
            value: `${hoursInQueue}h`,
            description: 'Longer wait time increases priority'
          });
        }
      } catch (e) {
        // Ignore date parsing errors
      }
    }

    return factors;
  };

  const factors = getFactors();

  return (
    <Box
      sx={{ display: 'inline-flex', alignItems: 'center', cursor: 'pointer' }}
      onMouseEnter={handlePopoverOpen}
      onMouseLeave={handlePopoverClose}
    >
      <Stack direction="row" spacing={1} alignItems="center">
        <Typography variant="body2" fontWeight="bold" sx={{ fontFamily: 'monospace', fontSize: '0.9rem' }}>
          {safeToFixed(score, 0)}
        </Typography>
        <Chip
          label={tier.label}
          size="small"
          color={tier.color}
          sx={{ height: 20, fontSize: '0.65rem', fontWeight: 600 }}
        />
        <InfoOutlinedIcon sx={{ fontSize: 16, color: 'text.secondary', opacity: 0.6 }} />
      </Stack>

      <Popover
        sx={{ pointerEvents: 'none' }}
        open={open}
        anchorEl={anchorEl}
        anchorOrigin={{
          vertical: 'top',
          horizontal: 'center',
        }}
        transformOrigin={{
          vertical: 'bottom',
          horizontal: 'center',
        }}
        onClose={handlePopoverClose}
        disableRestoreFocus
        slotProps={{
          paper: {
            sx: {
              p: 2,
              maxWidth: 350,
              bgcolor: 'background.paper',
              border: '1px solid',
              borderColor: 'divider',
            }
          }
        }}
      >
        <Box>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
            <Typography variant="subtitle2" fontWeight={600}>
              Priority Score
            </Typography>
            <Typography variant="h6" fontWeight={700} sx={{ fontFamily: 'monospace' }}>
              {safeToFixed(score, 0)}
            </Typography>
          </Box>

          <LinearProgress
            variant="determinate"
            value={Math.min((Math.log10(Math.max(score, 1)) / 7) * 100, 100)}
            sx={{
              height: 8,
              borderRadius: 4,
              mb: 2,
              bgcolor: tier.bgColor,
              '& .MuiLinearProgress-bar': {
                bgcolor: tier.color === 'error' ? 'error.main' :
                         tier.color === 'warning' ? 'warning.main' :
                         tier.color === 'info' ? 'info.main' : 'grey.500'
              }
            }}
          />

          {explanation && (
            <Box sx={{ mb: 2, p: 1.5, bgcolor: 'background.default', borderRadius: 1 }}>
              <Typography variant="caption" color="text.secondary" sx={{ fontStyle: 'italic' }}>
                {explanation}
              </Typography>
            </Box>
          )}

          {factors.length > 0 && (
            <>
              <Typography variant="caption" color="text.secondary" sx={{ mb: 1, display: 'block', fontWeight: 600 }}>
                Contributing Factors:
              </Typography>
              <Stack spacing={1}>
                {factors.map((factor, idx) => (
                  <Box
                    key={idx}
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 1,
                      p: 1,
                      bgcolor: 'background.default',
                      borderRadius: 1,
                    }}
                  >
                    <Box sx={{ color: 'primary.main' }}>
                      {factor.icon}
                    </Box>
                    <Box sx={{ flex: 1 }}>
                      <Typography variant="caption" fontWeight={600} sx={{ display: 'block' }}>
                        {factor.label}
                      </Typography>
                      <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.65rem' }}>
                        {factor.description}
                      </Typography>
                    </Box>
                    <Typography variant="caption" fontWeight={700} sx={{ fontFamily: 'monospace' }}>
                      {factor.value}
                    </Typography>
                  </Box>
                ))}
              </Stack>
            </>
          )}

          <Box sx={{ mt: 2, pt: 1.5, borderTop: '1px solid', borderColor: 'divider' }}>
            <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.65rem' }}>
              Higher scores are processed first. Score combines loss depth, wait time, and replacement count.
            </Typography>
          </Box>
        </Box>
      </Popover>
    </Box>
  );
};

export default PriorityScoreBreakdown;
