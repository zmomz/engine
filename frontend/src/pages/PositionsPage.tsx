import React, { useEffect, useState, useMemo } from 'react';
import {
  Box,
  Typography,
  Button,
  Collapse,
  IconButton,
  Paper,
  Tabs,
  Tab,
  Chip,
  Grid,
  Card,
  CardContent,
  Divider,
  Table,
  TableBody,
  TableCell,
  TableRow,
  useTheme,
  useMediaQuery,
  Tooltip
} from '@mui/material';
import { DataGrid, GridColDef, GridRenderCellParams, GridToolbar } from '@mui/x-data-grid';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import KeyboardArrowUpIcon from '@mui/icons-material/KeyboardArrowUp';
import RefreshIcon from '@mui/icons-material/Refresh';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import AccountBalanceWalletIcon from '@mui/icons-material/AccountBalanceWallet';
import ShowChartIcon from '@mui/icons-material/ShowChart';
import PercentIcon from '@mui/icons-material/Percent';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import PendingIcon from '@mui/icons-material/Pending';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import useConfirmStore from '../store/confirmStore';
import usePositionsStore, { PositionGroup } from '../store/positionsStore';
import { format } from 'date-fns';
import { PositionsPageSkeleton } from '../components/PositionsSkeleton';
import { MetricCard } from '../components/MetricCard';
import { useKeyboardShortcuts } from '../hooks/useKeyboardShortcuts';
import { useVisibilityRefresh } from '../hooks/useVisibilityRefresh';
import ResponsiveTableWrapper from '../components/ResponsiveTableWrapper';
import PositionCard from '../components/PositionCard';
import HistoryPositionCard from '../components/HistoryPositionCard';
import { safeToFixed, safeNumber, formatCompactCurrency, formatCompactPercent } from '../utils/formatters';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function CustomTabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;

  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      {...other}
      style={{ height: '100%', display: value === index ? 'block' : 'none' }}
    >
      {value === index && (
        <Box sx={{ p: 0, height: '100%' }}>
          {children}
        </Box>
      )}
    </div>
  );
}

const PositionsPage: React.FC = () => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  const {
    positions,
    positionHistory,
    loading,
    error,
    fetchPositions,
    fetchPositionHistory,
    closePosition
  } = usePositionsStore();
  const [expandedRows, setExpandedRows] = useState<Record<string, boolean>>({});
  const [tabValue, setTabValue] = useState(0);

  // Keyboard shortcuts
  useKeyboardShortcuts({
    onRefresh: () => {
      fetchPositions();
      fetchPositionHistory();
    },
  });

  // Refresh data when tab becomes visible again
  useVisibilityRefresh(() => {
    fetchPositions();
    if (tabValue === 1) fetchPositionHistory();
  });

  useEffect(() => {
    fetchPositions();
    fetchPositionHistory();

    // Set up polling for active positions (1 second for real-time feel)
    const interval = setInterval(() => {
      if (tabValue === 0) fetchPositions(true);
    }, 1000);

    return () => clearInterval(interval);
  }, [fetchPositions, fetchPositionHistory, tabValue]);

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
    if (newValue === 0) fetchPositions();
    if (newValue === 1) fetchPositionHistory();
  };

  const handleForceClose = async (groupId: string) => {
    const confirmed = await useConfirmStore.getState().requestConfirm({
      title: 'Force Close Position',
      message: 'Are you sure you want to force close this position group?',
      confirmText: 'Force Close',
      cancelText: 'Cancel'
    });

    if (confirmed) {
      await closePosition(groupId);
      fetchPositionHistory();
    }
  };

  const handleExpandClick = (groupId: string) => {
    setExpandedRows((prev) => ({
      ...prev,
      [groupId]: !prev[groupId],
    }));
  };

  const formatCurrency = (value: number | string | null | undefined) => {
    if (value === null || value === undefined) return '-';
    const numValue = typeof value === 'string' ? parseFloat(value) : value;
    if (isNaN(numValue)) return '-';
    return `$${numValue.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  };

  const getPnlColor = (value: number | string | null | undefined) => {
    if (value === null || value === undefined) return 'text.primary';
    const numValue = typeof value === 'string' ? parseFloat(value) : value;
    return numValue < 0 ? 'error.main' : 'success.main';
  };

  const formatDuration = (createdAt: string | null, closedAt: string | null) => {
    if (!createdAt || !closedAt) return '-';
    try {
      const start = new Date(createdAt);
      const end = new Date(closedAt);
      const durationMs = end.getTime() - start.getTime();
      const hours = Math.floor(durationMs / (1000 * 60 * 60));
      const minutes = Math.floor((durationMs % (1000 * 60 * 60)) / (1000 * 60));

      if (hours > 24) {
        const days = Math.floor(hours / 24);
        const remainingHours = hours % 24;
        return `${days}d ${remainingHours}h`;
      }
      return `${hours}h ${minutes}m`;
    } catch {
      return '-';
    }
  };

  const formatAge = (createdAt: string | null) => {
    if (!createdAt) return '-';
    try {
      const start = new Date(createdAt);
      const now = new Date();
      const durationMs = now.getTime() - start.getTime();
      const hours = Math.floor(durationMs / (1000 * 60 * 60));
      const minutes = Math.floor((durationMs % (1000 * 60 * 60)) / (1000 * 60));

      if (hours > 24) {
        const days = Math.floor(hours / 24);
        return `${days}d ${hours % 24}h`;
      }
      return `${hours}h ${minutes}m`;
    } catch {
      return '-';
    }
  };

  // Helper to format UUID - show first 8 chars
  const formatGroupId = (id: string) => {
    if (!id) return '-';
    return id.substring(0, 8);
  };

  // Calculate summary metrics for active positions
  const activeMetrics = useMemo(() => {
    const totalInvested = positions.reduce((sum, pos) => sum + safeNumber(pos.total_invested_usd), 0);
    const totalUnrealizedPnl = positions.reduce((sum, pos) => sum + safeNumber(pos.unrealized_pnl_usd), 0);
    const profitablePositions = positions.filter(p => safeNumber(p.unrealized_pnl_usd) > 0).length;

    // Calculate average age
    let avgAgeHours = 0;
    if (positions.length > 0) {
      const now = new Date();
      const totalAgeMs = positions.reduce((sum, pos) => {
        if (!pos.created_at) return sum;
        return sum + (now.getTime() - new Date(pos.created_at).getTime());
      }, 0);
      avgAgeHours = totalAgeMs / positions.length / (1000 * 60 * 60);
    }

    return {
      totalInvested,
      totalUnrealizedPnl,
      profitableCount: profitablePositions,
      totalCount: positions.length,
      avgAgeHours
    };
  }, [positions]);

  // Calculate summary metrics for history
  const historyMetrics = useMemo(() => {
    const totalRealizedPnl = positionHistory.reduce((sum, pos) => sum + safeNumber(pos.realized_pnl_usd), 0);
    const wins = positionHistory.filter(p => safeNumber(p.realized_pnl_usd) > 0).length;
    const losses = positionHistory.filter(p => safeNumber(p.realized_pnl_usd) < 0).length;
    const totalTrades = positionHistory.length;
    const winRate = totalTrades > 0 ? (wins / totalTrades) * 100 : 0;
    const avgTrade = totalTrades > 0 ? totalRealizedPnl / totalTrades : 0;

    return {
      totalRealizedPnl,
      wins,
      losses,
      totalTrades,
      winRate,
      avgTrade
    };
  }, [positionHistory]);

  const cellStyle = { fontSize: '0.813rem' };
  const monoStyle = { fontSize: '0.813rem', fontFamily: 'monospace' };

  const activeColumns: GridColDef[] = [
    {
      field: 'expand',
      headerName: '',
      width: 55,
      sortable: false,
      filterable: false,
      align: 'center',
      renderCell: (params: GridRenderCellParams<PositionGroup>) => (
        <IconButton
          aria-label="expand row"
          size="small"
          onClick={() => handleExpandClick(params.row.id)}
        >
          {expandedRows[params.row.id] ? <KeyboardArrowUpIcon /> : <KeyboardArrowDownIcon />}
        </IconButton>
      ),
    },
    {
      field: 'id',
      headerName: 'ID',
      width: 75,
      renderCell: (params) => (
        <Tooltip title={params.value}>
          <Typography sx={monoStyle}>
            {formatGroupId(params.value)}
          </Typography>
        </Tooltip>
      ),
    },
    {
      field: 'symbol',
      headerName: 'Symbol',
      width: 100,
      renderCell: (params: GridRenderCellParams<PositionGroup>) => (
        <Typography sx={{ ...cellStyle, fontWeight: 600 }}>{params.value}</Typography>
      )
    },
    {
      field: 'timeframe',
      headerName: 'TF',
      width: 55,
      align: 'center',
      headerAlign: 'center',
      renderCell: (params: GridRenderCellParams<PositionGroup>) => (
        <Typography sx={cellStyle}>{params.value}m</Typography>
      )
    },
    {
      field: 'exchange',
      headerName: 'Exchange',
      width: 85,
      renderCell: (params: GridRenderCellParams<PositionGroup>) => (
        <Typography sx={cellStyle}>{params.value}</Typography>
      )
    },
    {
      field: 'side',
      headerName: 'Side',
      width: 75,
      align: 'center',
      headerAlign: 'center',
      renderCell: (params) => (
        <Chip
          label={params.value?.toUpperCase()}
          color={params.value === 'long' ? 'success' : 'error'}
          size="small"
          variant="outlined"
          sx={{ fontSize: '0.7rem', height: 22 }}
        />
      )
    },
    {
      field: 'weighted_avg_entry',
      headerName: 'Entry',
      width: 85,
      align: 'right',
      headerAlign: 'right',
      renderCell: (params: GridRenderCellParams<PositionGroup>) => (
        <Typography sx={monoStyle}>
          {formatCompactCurrency(params.value)}
        </Typography>
      ),
    },
    {
      field: 'total_invested_usd',
      headerName: 'Invested',
      width: 80,
      align: 'right',
      headerAlign: 'right',
      renderCell: (params) => (
        <Typography sx={monoStyle}>
          {formatCompactCurrency(params.value)}
        </Typography>
      ),
    },
    {
      field: 'pyramid_count',
      headerName: 'Pyr',
      width: 55,
      align: 'center',
      headerAlign: 'center',
      renderCell: (params: GridRenderCellParams<PositionGroup>) => (
        <Typography sx={cellStyle}>
          {params.row.pyramid_count || 0}/{params.row.max_pyramids || 5}
        </Typography>
      ),
    },
    {
      field: 'filled_dca_legs',
      headerName: 'DCA',
      width: 55,
      align: 'center',
      headerAlign: 'center',
      renderCell: (params: GridRenderCellParams<PositionGroup>) => (
        <Typography sx={cellStyle}>
          {params.row.filled_dca_legs || 0}/{params.row.total_dca_legs || 0}
        </Typography>
      ),
    },
    {
      field: 'created_at',
      headerName: 'Age',
      width: 65,
      align: 'center',
      headerAlign: 'center',
      renderCell: (params: GridRenderCellParams<PositionGroup>) => (
        <Typography sx={cellStyle}>
          {formatAge(params.value)}
        </Typography>
      ),
    },
    {
      field: 'unrealized_pnl_usd',
      headerName: 'PnL',
      width: 80,
      align: 'right',
      headerAlign: 'right',
      renderCell: (params: GridRenderCellParams<PositionGroup>) => (
        <Typography sx={{ ...monoStyle, fontWeight: 600, color: getPnlColor(params.value) }}>
          {formatCompactCurrency(params.value)}
        </Typography>
      ),
    },
    {
      field: 'unrealized_pnl_percent',
      headerName: '%',
      width: 60,
      align: 'right',
      headerAlign: 'right',
      renderCell: (params: GridRenderCellParams<PositionGroup>) => (
        <Typography sx={{ ...monoStyle, fontWeight: 600, color: getPnlColor(params.value) }}>
          {formatCompactPercent(params.value)}
        </Typography>
      ),
    },
    {
      field: 'total_hedged_qty',
      headerName: 'Hedged Qty',
      width: 90,
      align: 'right',
      headerAlign: 'right',
      description: 'Cumulative quantity closed from this position to offset losers',
      renderHeader: () => (
        <Tooltip title="Cumulative quantity closed from this position to offset losers">
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            <Typography sx={{ fontSize: '0.813rem' }}>Hedged</Typography>
            <InfoOutlinedIcon sx={{ fontSize: 14, color: 'text.secondary' }} />
          </Box>
        </Tooltip>
      ),
      renderCell: (params: GridRenderCellParams<PositionGroup>) => {
        const value = safeNumber(params.row.total_hedged_qty);
        if (value === 0) {
          return <Typography sx={{ ...monoStyle, color: 'text.secondary' }}>-</Typography>;
        }
        return (
          <Tooltip title={`Total hedged: ${safeToFixed(value, 6)}`}>
            <Typography sx={{ ...monoStyle, color: 'info.main', fontWeight: 500 }}>
              {safeToFixed(value, 4)}
            </Typography>
          </Tooltip>
        );
      },
    },
    {
      field: 'total_hedged_value_usd',
      headerName: 'Hedge $',
      width: 80,
      align: 'right',
      headerAlign: 'right',
      description: 'Cumulative USD value of hedge closes',
      renderCell: (params: GridRenderCellParams<PositionGroup>) => {
        const value = safeNumber(params.row.total_hedged_value_usd);
        if (value === 0) {
          return <Typography sx={{ ...monoStyle, color: 'text.secondary' }}>-</Typography>;
        }
        return (
          <Typography sx={{ ...monoStyle, color: 'info.main', fontWeight: 500 }}>
            {formatCompactCurrency(value)}
          </Typography>
        );
      },
    },
    {
      field: 'actions',
      headerName: '',
      width: 95,
      sortable: false,
      align: 'center',
      renderCell: (params: GridRenderCellParams<PositionGroup>) => (
        <Button
          variant="contained"
          color="error"
          size="small"
          onClick={() => handleForceClose(params.row.id)}
          disabled={params.row.status === 'CLOSING' || params.row.status === 'CLOSED'}
          sx={{ fontSize: '0.75rem', minWidth: 65 }}
        >
          Close
        </Button>
      ),
    },
  ];

  const historyColumns: GridColDef[] = [
    {
      field: 'id',
      headerName: 'ID',
      width: 75,
      renderCell: (params) => (
        <Tooltip title={params.value}>
          <Typography sx={monoStyle}>
            {formatGroupId(params.value)}
          </Typography>
        </Tooltip>
      ),
    },
    {
      field: 'symbol',
      headerName: 'Symbol',
      width: 100,
      renderCell: (params: GridRenderCellParams<PositionGroup>) => (
        <Typography sx={{ ...cellStyle, fontWeight: 600 }}>{params.value}</Typography>
      )
    },
    {
      field: 'timeframe',
      headerName: 'TF',
      width: 55,
      align: 'center',
      headerAlign: 'center',
      renderCell: (params: GridRenderCellParams<PositionGroup>) => (
        <Typography sx={cellStyle}>{params.value}m</Typography>
      )
    },
    {
      field: 'exchange',
      headerName: 'Exchange',
      width: 85,
      renderCell: (params: GridRenderCellParams<PositionGroup>) => (
        <Typography sx={cellStyle}>{params.value}</Typography>
      )
    },
    {
      field: 'side',
      headerName: 'Side',
      width: 75,
      align: 'center',
      headerAlign: 'center',
      renderCell: (params) => (
        <Chip
          label={params.value?.toUpperCase()}
          color={params.value === 'long' ? 'success' : 'error'}
          size="small"
          variant="outlined"
          sx={{ fontSize: '0.7rem', height: 22 }}
        />
      )
    },
    {
      field: 'weighted_avg_entry',
      headerName: 'Entry',
      width: 85,
      align: 'right',
      headerAlign: 'right',
      renderCell: (params) => (
        <Typography sx={monoStyle}>
          {formatCompactCurrency(params.value)}
        </Typography>
      ),
    },
    {
      field: 'total_invested_usd',
      headerName: 'Invested',
      width: 80,
      align: 'right',
      headerAlign: 'right',
      renderCell: (params) => (
        <Typography sx={monoStyle}>
          {formatCompactCurrency(params.value)}
        </Typography>
      ),
    },
    {
      field: 'pyramid_count',
      headerName: 'Pyr',
      width: 50,
      align: 'center',
      headerAlign: 'center',
      renderCell: (params: GridRenderCellParams<PositionGroup>) => (
        <Typography sx={cellStyle}>
          {params.row.pyramid_count || 0}
        </Typography>
      ),
    },
    {
      field: 'realized_pnl_usd',
      headerName: 'PnL',
      width: 80,
      align: 'right',
      headerAlign: 'right',
      renderCell: (params: GridRenderCellParams<PositionGroup>) => (
        <Typography sx={{ ...monoStyle, fontWeight: 600, color: getPnlColor(params.value) }}>
          {formatCompactCurrency(params.value)}
        </Typography>
      ),
    },
    {
      field: 'realized_pnl_percent',
      headerName: '%',
      width: 60,
      align: 'right',
      headerAlign: 'right',
      renderCell: (params: GridRenderCellParams<PositionGroup>) => {
        const pnl = safeNumber(params.row.realized_pnl_usd);
        const invested = safeNumber(params.row.total_invested_usd);
        const pnlPercent = invested > 0 ? (pnl / invested) * 100 : 0;
        return (
          <Typography sx={{ ...monoStyle, fontWeight: 600, color: getPnlColor(pnlPercent) }}>
            {formatCompactPercent(pnlPercent)}
          </Typography>
        );
      },
    },
    {
      field: 'total_hedged_qty',
      headerName: 'Hedged',
      width: 80,
      align: 'right',
      headerAlign: 'right',
      description: 'Quantity used to offset losers',
      renderCell: (params: GridRenderCellParams<PositionGroup>) => {
        const value = safeNumber(params.row.total_hedged_qty);
        if (value === 0) {
          return <Typography sx={{ ...monoStyle, color: 'text.secondary' }}>-</Typography>;
        }
        return (
          <Typography sx={{ ...monoStyle, color: 'info.main' }}>
            {safeToFixed(value, 4)}
          </Typography>
        );
      },
    },
    {
      field: 'total_hedged_value_usd',
      headerName: 'Hedge $',
      width: 75,
      align: 'right',
      headerAlign: 'right',
      description: 'USD value of hedge closes',
      renderCell: (params: GridRenderCellParams<PositionGroup>) => {
        const value = safeNumber(params.row.total_hedged_value_usd);
        if (value === 0) {
          return <Typography sx={{ ...monoStyle, color: 'text.secondary' }}>-</Typography>;
        }
        return (
          <Typography sx={{ ...monoStyle, color: 'info.main' }}>
            {formatCompactCurrency(value)}
          </Typography>
        );
      },
    },
    {
      field: 'duration',
      headerName: 'Duration',
      width: 80,
      align: 'center',
      headerAlign: 'center',
      renderCell: (params: GridRenderCellParams<PositionGroup>) => (
        <Typography sx={cellStyle}>
          {formatDuration(params.row.created_at, params.row.closed_at)}
        </Typography>
      ),
    },
    {
      field: 'closed_at',
      headerName: 'Closed',
      width: 115,
      align: 'center',
      headerAlign: 'center',
      renderCell: (params) => (
        <Typography sx={cellStyle}>
          {params.value ? format(new Date(params.value), 'MMM d, HH:mm') : '-'}
        </Typography>
      )
    },
  ];

  // Show skeleton on initial load
  if (loading && positions.length === 0 && positionHistory.length === 0) {
    return <PositionsPageSkeleton />;
  }

  return (
    <Box sx={{ flexGrow: 1, p: { xs: 2, sm: 3 }, minHeight: '85vh', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <Box sx={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        mb: 2,
        flexWrap: 'wrap',
        gap: 1
      }}>
        <Typography variant="h4" sx={{ fontSize: { xs: '1.75rem', sm: '2.125rem' } }}>
          Positions
        </Typography>
        <IconButton
          onClick={() => { fetchPositions(); fetchPositionHistory(); }}
          color="primary"
          size="medium"
        >
          <RefreshIcon />
        </IconButton>
      </Box>

      {error && <Typography color="error" sx={{ mb: 2 }}>{error}</Typography>}

      {/* Summary Cards - Different for each tab */}
      <Grid container spacing={{ xs: 2, sm: 3 }} sx={{ mb: 3 }}>
        {tabValue === 0 ? (
          // Active Positions Summary
          <>
            <Grid size={{ xs: 6, sm: 6, md: 3 }}>
              <MetricCard
                label="Total Invested"
                value={formatCurrency(activeMetrics.totalInvested)}
                subtitle={`${activeMetrics.totalCount} position${activeMetrics.totalCount !== 1 ? 's' : ''}`}
                icon={<AccountBalanceWalletIcon />}
                colorScheme="neutral"
                variant="small"
              />
            </Grid>
            <Grid size={{ xs: 6, sm: 6, md: 3 }}>
              <MetricCard
                label="Unrealized PnL"
                value={formatCurrency(activeMetrics.totalUnrealizedPnl)}
                trend={activeMetrics.totalUnrealizedPnl >= 0 ? 'up' : 'down'}
                icon={<TrendingUpIcon />}
                colorScheme={activeMetrics.totalUnrealizedPnl >= 0 ? 'bullish' : 'bearish'}
                variant="small"
              />
            </Grid>
            <Grid size={{ xs: 6, sm: 6, md: 3 }}>
              <MetricCard
                label="Profitable"
                value={`${activeMetrics.profitableCount}/${activeMetrics.totalCount}`}
                subtitle={activeMetrics.totalCount > 0 ? `${safeToFixed((activeMetrics.profitableCount / activeMetrics.totalCount) * 100, 0)}% in profit` : 'No positions'}
                icon={<PercentIcon />}
                colorScheme="neutral"
                variant="small"
              />
            </Grid>
            <Grid size={{ xs: 6, sm: 6, md: 3 }}>
              <MetricCard
                label="Avg Age"
                value={activeMetrics.avgAgeHours > 24 ? `${safeToFixed(activeMetrics.avgAgeHours / 24, 1)}d` : `${safeToFixed(activeMetrics.avgAgeHours, 1)}h`}
                icon={<AccessTimeIcon />}
                colorScheme="neutral"
                variant="small"
              />
            </Grid>
          </>
        ) : (
          // History Summary
          <>
            <Grid size={{ xs: 6, sm: 6, md: 3 }}>
              <MetricCard
                label="Total Trades"
                value={historyMetrics.totalTrades.toString()}
                subtitle={`${historyMetrics.wins}W / ${historyMetrics.losses}L`}
                icon={<ShowChartIcon />}
                colorScheme="neutral"
                variant="small"
              />
            </Grid>
            <Grid size={{ xs: 6, sm: 6, md: 3 }}>
              <MetricCard
                label="Realized PnL"
                value={formatCurrency(historyMetrics.totalRealizedPnl)}
                trend={historyMetrics.totalRealizedPnl >= 0 ? 'up' : 'down'}
                icon={<TrendingUpIcon />}
                colorScheme={historyMetrics.totalRealizedPnl >= 0 ? 'bullish' : 'bearish'}
                variant="small"
              />
            </Grid>
            <Grid size={{ xs: 6, sm: 6, md: 3 }}>
              <MetricCard
                label="Win Rate"
                value={`${safeToFixed(historyMetrics.winRate, 1)}%`}
                subtitle={`${historyMetrics.wins} wins`}
                icon={<PercentIcon />}
                colorScheme={historyMetrics.winRate >= 50 ? 'bullish' : 'bearish'}
                variant="small"
              />
            </Grid>
            <Grid size={{ xs: 6, sm: 6, md: 3 }}>
              <MetricCard
                label="Avg Trade"
                value={formatCurrency(historyMetrics.avgTrade)}
                trend={historyMetrics.avgTrade >= 0 ? 'up' : 'down'}
                icon={<TrendingUpIcon />}
                colorScheme={historyMetrics.avgTrade >= 0 ? 'bullish' : 'bearish'}
                variant="small"
              />
            </Grid>
          </>
        )}
      </Grid>

      <Paper sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minHeight: 400 }}>
        <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
          <Tabs
            value={tabValue}
            onChange={handleTabChange}
            aria-label="positions tabs"
            variant="scrollable"
            scrollButtons="auto"
            allowScrollButtonsMobile
          >
            <Tab
              label={`Active (${positions.length})`}
              sx={{ fontSize: { xs: '0.75rem', sm: '0.875rem' } }}
            />
            <Tab
              label={`History (${positionHistory.length})`}
              sx={{ fontSize: { xs: '0.75rem', sm: '0.875rem' } }}
            />
          </Tabs>
        </Box>

        <Box sx={{ flexGrow: 1, overflow: isMobile ? 'auto' : 'hidden' }}>
          <CustomTabPanel value={tabValue} index={0}>
            {isMobile ? (
              <Box sx={{ p: 2, pt: 1 }}>
                {positions.length > 0 ? (
                  positions.map((position) => (
                    <PositionCard
                      key={position.id}
                      position={position}
                      onForceClose={handleForceClose}
                    />
                  ))
                ) : (
                  <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'center', py: 4 }}>
                    No active positions
                  </Typography>
                )}
              </Box>
            ) : (
              <ResponsiveTableWrapper>
                <DataGrid
                  rows={positions}
                  columns={activeColumns}
                  getRowId={(row) => row.id}
                  loading={loading}
                  disableRowSelectionOnClick
                  slots={{ toolbar: GridToolbar }}
                  initialState={{
                    pagination: { paginationModel: { pageSize: 10 } },
                  }}
                  pageSizeOptions={[5, 10, 20]}
                />
              </ResponsiveTableWrapper>
            )}
          </CustomTabPanel>

          <CustomTabPanel value={tabValue} index={1}>
            {isMobile ? (
              <Box sx={{ p: 2, pt: 1 }}>
                {positionHistory.length > 0 ? (
                  [...positionHistory]
                    .sort((a, b) => new Date(b.closed_at || 0).getTime() - new Date(a.closed_at || 0).getTime())
                    .map((position) => (
                      <HistoryPositionCard
                        key={position.id}
                        position={position}
                      />
                    ))
                ) : (
                  <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'center', py: 4 }}>
                    No position history
                  </Typography>
                )}
              </Box>
            ) : (
              <ResponsiveTableWrapper>
                <DataGrid
                  rows={positionHistory}
                  columns={historyColumns}
                  getRowId={(row) => row.id}
                  loading={loading}
                  disableRowSelectionOnClick
                  slots={{ toolbar: GridToolbar }}
                  initialState={{
                    sorting: {
                      sortModel: [{ field: 'closed_at', sort: 'desc' }],
                    },
                    pagination: { paginationModel: { pageSize: 10 } },
                  }}
                  pageSizeOptions={[5, 10, 20, 50]}
                />
              </ResponsiveTableWrapper>
            )}
          </CustomTabPanel>
        </Box>
      </Paper>

      {/* Expanded pyramid details for active positions */}
      {tabValue === 0 && positions.map((position) => (
        <Collapse in={expandedRows[position.id]} key={position.id} timeout="auto" unmountOnExit>
          <Box sx={{ m: 2, ml: { xs: 2, sm: 4 } }}>
            <Card variant="outlined" sx={{ bgcolor: 'background.default' }}>
              <CardContent>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <IconButton
                      size="small"
                      onClick={() => handleExpandClick(position.id)}
                      sx={{ mr: 1 }}
                    >
                      <KeyboardArrowUpIcon />
                    </IconButton>
                    <Typography variant="h6" sx={{ fontWeight: 600, fontSize: '1rem' }}>
                      {position.symbol} - {position.side.toUpperCase()} Details
                    </Typography>
                  </Box>
                  <Button
                    variant="contained"
                    size="small"
                    color="error"
                    onClick={() => handleForceClose(position.id)}
                    disabled={position.status === 'CLOSING' || position.status === 'CLOSED'}
                    sx={{ fontSize: '0.75rem' }}
                  >
                    Force Close
                  </Button>
                </Box>

                <Divider sx={{ mb: 2 }} />

                {/* Position Summary */}
                <Grid container spacing={2} sx={{ mb: 3 }}>
                  <Grid size={{ xs: 6, sm: 3 }}>
                    <Typography variant="caption" color="text.secondary">Base Entry</Typography>
                    <Typography variant="body2" fontWeight={600} sx={{ fontFamily: 'monospace' }}>
                      {formatCurrency(position.base_entry_price)}
                    </Typography>
                  </Grid>
                  <Grid size={{ xs: 6, sm: 3 }}>
                    <Typography variant="caption" color="text.secondary">Avg Entry</Typography>
                    <Typography variant="body2" fontWeight={600} sx={{ fontFamily: 'monospace' }}>
                      {formatCurrency(position.weighted_avg_entry)}
                    </Typography>
                  </Grid>
                  <Grid size={{ xs: 6, sm: 3 }}>
                    <Typography variant="caption" color="text.secondary">Total Quantity</Typography>
                    <Typography variant="body2" fontWeight={600} sx={{ fontFamily: 'monospace' }}>
                      {safeToFixed(position.total_filled_quantity, 4)}
                    </Typography>
                  </Grid>
                  <Grid size={{ xs: 6, sm: 3 }}>
                    <Typography variant="caption" color="text.secondary">TP Mode</Typography>
                    <Typography variant="body2" fontWeight={600}>
                      {position.tp_mode.replace('_', ' ').toUpperCase()}
                    </Typography>
                  </Grid>
                </Grid>

                {/* Pyramids Section */}
                <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 600 }}>
                  Pyramids ({position.pyramid_count}/{position.max_pyramids})
                </Typography>

                {position.pyramids && position.pyramids.length > 0 ? (
                  <Grid container spacing={2}>
                    {position.pyramids.map((pyramid, idx) => (
                      <Grid size={{ xs: 12, md: 6 }} key={pyramid.id}>
                        <Card variant="outlined" sx={{ bgcolor: 'background.paper' }}>
                          <CardContent sx={{ p: 2 }}>
                            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                              <Typography variant="body2" fontWeight={600}>
                                Pyramid #{idx}
                              </Typography>
                              <Chip
                                label={pyramid.status}
                                size="small"
                                color={pyramid.status === 'FILLED' ? 'success' : 'warning'}
                                icon={pyramid.status === 'FILLED' ? <CheckCircleIcon /> : <PendingIcon />}
                              />
                            </Box>

                            <Typography variant="caption" color="text.secondary">Entry Price</Typography>
                            <Typography variant="body2" sx={{ mb: 1, fontFamily: 'monospace' }}>
                              {formatCurrency(pyramid.entry_price)}
                            </Typography>

                            {/* DCA Orders */}
                            {pyramid.dca_orders && pyramid.dca_orders.length > 0 && (
                              <>
                                <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                                  DCA Orders ({pyramid.dca_orders.length})
                                </Typography>
                                <Table size="small" sx={{ mt: 0.5 }}>
                                  <TableBody>
                                    {pyramid.dca_orders.map((dca) => (
                                      <TableRow key={dca.id}>
                                        <TableCell sx={{ py: 0.5, px: 1, fontSize: '0.7rem', borderBottom: 'none' }}>
                                          {dca.order_type}
                                        </TableCell>
                                        <TableCell sx={{ py: 0.5, px: 1, fontSize: '0.7rem', fontFamily: 'monospace', borderBottom: 'none' }}>
                                          {formatCurrency(dca.price)}
                                        </TableCell>
                                        <TableCell sx={{ py: 0.5, px: 1, fontSize: '0.7rem', fontFamily: 'monospace', borderBottom: 'none' }}>
                                          Qty: {safeToFixed(dca.quantity, 4)}
                                        </TableCell>
                                        <TableCell sx={{ py: 0.5, px: 1, borderBottom: 'none' }}>
                                          <Chip
                                            label={dca.status}
                                            size="small"
                                            color={dca.status === 'FILLED' ? 'success' : dca.status === 'OPEN' ? 'info' : 'default'}
                                            sx={{ height: 16, fontSize: '0.65rem' }}
                                          />
                                        </TableCell>
                                      </TableRow>
                                    ))}
                                  </TableBody>
                                </Table>
                              </>
                            )}
                          </CardContent>
                        </Card>
                      </Grid>
                    ))}
                  </Grid>
                ) : (
                  <Typography variant="body2" color="text.secondary" sx={{ fontStyle: 'italic' }}>
                    No pyramids found for this position group.
                  </Typography>
                )}

                {/* Risk Information */}
                <Divider sx={{ my: 2 }} />
                <Grid container spacing={2}>
                  <Grid size={{ xs: 6, sm: 3 }}>
                    <Typography variant="caption" color="text.secondary">Status</Typography>
                    <Typography variant="body2">
                      <Chip label={position.status} size="small" variant="outlined" />
                    </Typography>
                  </Grid>
                  <Grid size={{ xs: 6, sm: 3 }}>
                    <Typography variant="caption" color="text.secondary">Risk Eligible</Typography>
                    <Typography variant="body2" color={position.risk_eligible ? 'success.main' : 'text.secondary'}>
                      {position.risk_eligible ? 'Yes' : 'No'}
                    </Typography>
                  </Grid>
                  <Grid size={{ xs: 6, sm: 3 }}>
                    <Typography variant="caption" color="text.secondary">Risk Blocked</Typography>
                    <Typography variant="body2" color={position.risk_blocked ? 'error.main' : 'success.main'}>
                      {position.risk_blocked ? 'Yes' : 'No'}
                    </Typography>
                  </Grid>
                  <Grid size={{ xs: 6, sm: 3 }}>
                    <Typography variant="caption" color="text.secondary">Created</Typography>
                    <Typography variant="body2" sx={{ fontSize: '0.75rem' }}>
                      {position.created_at ? format(new Date(position.created_at), 'MMM d, h:mm a') : '-'}
                    </Typography>
                  </Grid>
                </Grid>

                {/* Risk Timer */}
                {position.risk_timer_expires && (
                  <Box sx={{ mt: 2, p: 1.5, bgcolor: 'warning.dark', borderRadius: 1 }}>
                    <Typography variant="body2" color="warning.contrastText">
                      ⏱️ Risk Timer: {new Date(position.risk_timer_expires).toLocaleString()}
                    </Typography>
                  </Box>
                )}
              </CardContent>
            </Card>
          </Box>
        </Collapse>
      ))}
    </Box>
  );
};

export default PositionsPage;
