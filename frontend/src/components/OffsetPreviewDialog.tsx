import React from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Typography,
  Divider,
  Table,
  TableBody,
  TableCell,
  TableRow,
  Chip,
  Stack,
  Alert
} from '@mui/material';
import TrendingDownIcon from '@mui/icons-material/TrendingDown';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import { safeToFixed, safeNumber } from '../utils/formatters';

export interface OffsetPreviewData {
  loser: {
    id: string;
    symbol: string;
    unrealized_pnl_percent: number;
    unrealized_pnl_usd: number;
    pyramid_count: number;
    max_pyramids: number;
    age_minutes: number;
  };
  winners: Array<{
    symbol: string;
    profit_available: number;
    amount_to_close: number;
    partial: boolean;
  }>;
  required_offset_usd: number;
  total_available_profit: number;
}

export interface OffsetPreviewDialogProps {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  data: OffsetPreviewData | null;
  loading?: boolean;
}

export const OffsetPreviewDialog: React.FC<OffsetPreviewDialogProps> = ({
  open,
  onClose,
  onConfirm,
  data,
  loading = false
}) => {
  if (!data) return null;

  const canExecute = data.total_available_profit >= data.required_offset_usd;
  const executionDetails = canExecute
    ? 'This offset will be executed immediately.'
    : 'Insufficient profit available to execute this offset.';

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="sm"
      fullWidth
      PaperProps={{
        sx: {
          bgcolor: 'background.paper',
          backgroundImage: 'none',
        }
      }}
    >
      <DialogTitle sx={{ pb: 1 }}>
        <Stack direction="row" spacing={1} alignItems="center">
          <InfoOutlinedIcon color="primary" />
          <Typography variant="h6" component="span">
            Offset Preview
          </Typography>
        </Stack>
      </DialogTitle>

      <DialogContent dividers>
        <Box sx={{ mb: 3 }}>
          <Typography variant="subtitle2" color="text.secondary" gutterBottom>
            Losing Position
          </Typography>
          <Box
            sx={{
              p: 2,
              bgcolor: 'error.dark',
              borderRadius: 2,
              border: '1px solid',
              borderColor: 'error.main',
            }}
          >
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
              <Typography variant="h6" fontWeight={700}>
                {data.loser.symbol}
              </Typography>
              <Chip
                icon={<TrendingDownIcon />}
                label={`${safeToFixed(data.loser.unrealized_pnl_percent)}%`}
                color="error"
                size="small"
              />
            </Box>
            <Table size="small">
              <TableBody>
                <TableRow>
                  <TableCell sx={{ border: 0, color: 'error.contrastText', py: 0.5 }}>Loss (USD)</TableCell>
                  <TableCell align="right" sx={{ border: 0, color: 'error.contrastText', py: 0.5, fontFamily: 'monospace', fontWeight: 600 }}>
                    ${safeToFixed(Math.abs(safeNumber(data.loser.unrealized_pnl_usd)))}
                  </TableCell>
                </TableRow>
                <TableRow>
                  <TableCell sx={{ border: 0, color: 'error.contrastText', py: 0.5 }}>Age</TableCell>
                  <TableCell align="right" sx={{ border: 0, color: 'error.contrastText', py: 0.5, fontFamily: 'monospace' }}>
                    {data.loser.age_minutes} min
                  </TableCell>
                </TableRow>
                <TableRow>
                  <TableCell sx={{ border: 0, color: 'error.contrastText', py: 0.5 }}>Pyramids</TableCell>
                  <TableCell align="right" sx={{ border: 0, color: 'error.contrastText', py: 0.5, fontFamily: 'monospace' }}>
                    {data.loser.pyramid_count}/{data.loser.max_pyramids}
                  </TableCell>
                </TableRow>
              </TableBody>
            </Table>
          </Box>
        </Box>

        <Divider sx={{ my: 2 }} />

        <Box sx={{ mb: 3 }}>
          <Typography variant="subtitle2" color="text.secondary" gutterBottom>
            Offset Plan ({data.winners.length} winner{data.winners.length !== 1 ? 's' : ''})
          </Typography>
          <Stack spacing={1.5}>
            {data.winners.map((winner, idx) => (
              <Box
                key={idx}
                sx={{
                  p: 2,
                  bgcolor: 'success.dark',
                  borderRadius: 2,
                  border: '1px solid',
                  borderColor: 'success.main',
                }}
              >
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                  <Typography variant="body1" fontWeight={600} sx={{ color: 'success.contrastText' }}>
                    {winner.symbol}
                  </Typography>
                  <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                    {winner.partial && (
                      <Chip label="Partial" size="small" color="warning" sx={{ height: 20 }} />
                    )}
                    <Chip
                      icon={<TrendingUpIcon />}
                      label={`$${safeToFixed(winner.amount_to_close)}`}
                      color="success"
                      size="small"
                    />
                  </Box>
                </Box>
                <Typography variant="caption" sx={{ color: 'success.contrastText', opacity: 0.9 }}>
                  Available: ${safeToFixed(winner.profit_available)}
                </Typography>
              </Box>
            ))}
          </Stack>
        </Box>

        <Divider sx={{ my: 2 }} />

        <Box sx={{ mb: 2 }}>
          <Table size="small">
            <TableBody>
              <TableRow>
                <TableCell sx={{ border: 0, py: 0.5 }}>
                  <Typography variant="body2" fontWeight={600}>Required Offset</Typography>
                </TableCell>
                <TableCell align="right" sx={{ border: 0, py: 0.5 }}>
                  <Typography variant="body2" fontWeight={700} sx={{ fontFamily: 'monospace', color: 'error.main' }}>
                    ${safeToFixed(data.required_offset_usd)}
                  </Typography>
                </TableCell>
              </TableRow>
              <TableRow>
                <TableCell sx={{ border: 0, py: 0.5 }}>
                  <Typography variant="body2" fontWeight={600}>Available Profit</Typography>
                </TableCell>
                <TableCell align="right" sx={{ border: 0, py: 0.5 }}>
                  <Typography variant="body2" fontWeight={700} sx={{ fontFamily: 'monospace', color: 'success.main' }}>
                    ${safeToFixed(data.total_available_profit)}
                  </Typography>
                </TableCell>
              </TableRow>
              <TableRow>
                <TableCell sx={{ border: 0, pt: 1 }}>
                  <Typography variant="body2" fontWeight={600}>Net Result</Typography>
                </TableCell>
                <TableCell align="right" sx={{ border: 0, pt: 1 }}>
                  <Typography
                    variant="body2"
                    fontWeight={700}
                    sx={{
                      fontFamily: 'monospace',
                      color: (data.total_available_profit - data.required_offset_usd) >= 0 ? 'success.main' : 'error.main'
                    }}
                  >
                    ${safeToFixed(safeNumber(data.total_available_profit) - safeNumber(data.required_offset_usd))}
                  </Typography>
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </Box>

        {!canExecute && (
          <Alert severity="warning" sx={{ mt: 2 }}>
            Insufficient profit to execute this offset. Additional winning positions needed.
          </Alert>
        )}

        {canExecute && (
          <Alert severity="info" sx={{ mt: 2 }}>
            {executionDetails}
          </Alert>
        )}
      </DialogContent>

      <DialogActions sx={{ px: 3, py: 2 }}>
        <Button onClick={onClose} color="inherit">
          Cancel
        </Button>
        <Button
          onClick={onConfirm}
          variant="contained"
          color="error"
          disabled={!canExecute || loading}
          sx={{ minWidth: 120 }}
        >
          {loading ? 'Executing...' : 'Execute Offset'}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default OffsetPreviewDialog;
