import React, { useEffect, useState, useMemo } from 'react';
import {
  Box,
  Typography,
  Grid,
  Card,
  CardContent,
  ToggleButton,
  ToggleButtonGroup,
  Table,
  TableBody,
  TableCell,
  TableRow,
  TableHead,
  Chip,
  Skeleton,
  Button,
  Menu,
  MenuItem,
  ListItemIcon,
  ListItemText,
  LinearProgress,
  IconButton
} from '@mui/material';
import DownloadIcon from '@mui/icons-material/Download';
import TableChartIcon from '@mui/icons-material/TableChart';
import DescriptionIcon from '@mui/icons-material/Description';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import TrendingDownIcon from '@mui/icons-material/TrendingDown';
import RefreshIcon from '@mui/icons-material/Refresh';
import {
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  AreaChart,
  Area,
  BarChart,
  Bar,
  Cell
} from 'recharts';
import { format, subDays, subHours, isAfter, parseISO } from 'date-fns';
import usePositionsStore from '../store/positionsStore';
import useDashboardStore from '../store/dashboardStore';
import { DataFreshnessIndicator } from '../components/DataFreshnessIndicator';
import { useKeyboardShortcuts } from '../hooks/useKeyboardShortcuts';
import { safeToFixed, safeNumber } from '../utils/formatters';

type TimeRange = '24h' | '7d' | '30d' | 'all';

const AnalyticsPage: React.FC = () => {
  const { positionHistory, fetchPositionHistory, loading } = usePositionsStore();
  const { data: dashboardData, fetchDashboardData, loading: dashboardLoading } = useDashboardStore();
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [timeRange, setTimeRange] = useState<TimeRange>('30d');
  const [exportAnchorEl, setExportAnchorEl] = useState<null | HTMLElement>(null);
  const exportMenuOpen = Boolean(exportAnchorEl);

  useKeyboardShortcuts({
    onRefresh: () => {
      fetchPositionHistory();
      fetchDashboardData();
      setLastUpdated(new Date());
    },
  });

  useEffect(() => {
    const fetchData = async () => {
      await Promise.all([
        fetchPositionHistory(),
        fetchDashboardData()
      ]);
      setLastUpdated(new Date());
    };
    fetchData();
  }, [fetchPositionHistory, fetchDashboardData]);

  const perf = dashboardData?.performance_dashboard;

  // Filter positions by time range
  const filteredPositions = useMemo(() => {
    if (!positionHistory || positionHistory.length === 0) return [];

    const now = new Date();
    let cutoffDate: Date;

    switch (timeRange) {
      case '24h':
        cutoffDate = subHours(now, 24);
        break;
      case '7d':
        cutoffDate = subDays(now, 7);
        break;
      case '30d':
        cutoffDate = subDays(now, 30);
        break;
      case 'all':
      default:
        return positionHistory.filter(p => p.closed_at);
    }

    return positionHistory.filter(p => {
      if (!p.closed_at) return false;
      try {
        const closedAt = parseISO(p.closed_at);
        return isAfter(closedAt, cutoffDate);
      } catch {
        return false;
      }
    });
  }, [positionHistory, timeRange]);

  const getPnl = (p: any): number => {
    const val = p.realized_pnl_usd;
    if (val === null || val === undefined) return 0;
    const num = typeof val === 'string' ? parseFloat(val) : val;
    return typeof num === 'number' && !isNaN(num) ? num : 0;
  };

  // Calculate metrics from filtered positions
  const metrics = useMemo(() => {
    if (filteredPositions.length === 0) {
      return {
        totalTrades: 0,
        winningTrades: 0,
        losingTrades: 0,
        winRate: 0,
        totalPnl: 0,
        avgWin: 0,
        avgLoss: 0,
        profitFactor: 0,
        largestWin: 0,
        largestLoss: 0,
        avgHoldTime: 0,
      };
    }

    const wins = filteredPositions.filter(p => getPnl(p) > 0);
    const losses = filteredPositions.filter(p => getPnl(p) < 0);

    const totalPnl = filteredPositions.reduce((sum, p) => sum + getPnl(p), 0);
    const totalWins = wins.reduce((sum, p) => sum + getPnl(p), 0);
    const totalLosses = Math.abs(losses.reduce((sum, p) => sum + getPnl(p), 0));

    const avgWin = wins.length > 0 ? totalWins / wins.length : 0;
    const avgLoss = losses.length > 0 ? totalLosses / losses.length : 0;

    const largestWin = wins.length > 0 ? Math.max(...wins.map(p => getPnl(p))) : 0;
    const largestLoss = losses.length > 0 ? Math.min(...losses.map(p => getPnl(p))) : 0;

    let totalHoldTime = 0;
    let validHoldTimeCount = 0;
    filteredPositions.forEach(p => {
      if (p.created_at && p.closed_at) {
        try {
          const created = parseISO(p.created_at);
          const closed = parseISO(p.closed_at);
          const hours = (closed.getTime() - created.getTime()) / (1000 * 60 * 60);
          totalHoldTime += hours;
          validHoldTimeCount++;
        } catch {}
      }
    });

    return {
      totalTrades: filteredPositions.length,
      winningTrades: wins.length,
      losingTrades: losses.length,
      winRate: filteredPositions.length > 0 ? (wins.length / filteredPositions.length) * 100 : 0,
      totalPnl,
      avgWin,
      avgLoss,
      profitFactor: totalLosses > 0 ? totalWins / totalLosses : totalWins > 0 ? Infinity : 0,
      largestWin,
      largestLoss,
      avgHoldTime: validHoldTimeCount > 0 ? totalHoldTime / validHoldTimeCount : 0,
    };
  }, [filteredPositions]);

  // Equity curve data
  const equityCurveData = useMemo(() => {
    if (filteredPositions.length === 0) return [];

    const sorted = [...filteredPositions]
      .filter(p => p.closed_at)
      .sort((a, b) => {
        try {
          return parseISO(a.closed_at!).getTime() - parseISO(b.closed_at!).getTime();
        } catch {
          return 0;
        }
      });

    let cumulative = 0;
    return sorted.map((p, idx) => {
      const pnl = getPnl(p);
      cumulative += pnl;
      return {
        trade: idx + 1,
        date: p.closed_at ? format(parseISO(p.closed_at), 'MMM d') : '',
        pnl,
        cumulative,
        symbol: p.symbol,
      };
    });
  }, [filteredPositions]);

  // Pair performance data
  const pairPerformance = useMemo(() => {
    if (filteredPositions.length === 0) return [];

    const pairMap: Record<string, { pnl: number; trades: number; wins: number }> = {};

    filteredPositions.forEach(p => {
      if (!pairMap[p.symbol]) {
        pairMap[p.symbol] = { pnl: 0, trades: 0, wins: 0 };
      }
      const pnl = getPnl(p);
      pairMap[p.symbol].pnl += pnl;
      pairMap[p.symbol].trades += 1;
      if (pnl > 0) pairMap[p.symbol].wins += 1;
    });

    return Object.entries(pairMap)
      .map(([symbol, data]) => ({
        symbol,
        pnl: data.pnl,
        trades: data.trades,
        winRate: (data.wins / data.trades) * 100,
      }))
      .sort((a, b) => b.pnl - a.pnl);
  }, [filteredPositions]);

  // PnL by day of week
  const dayOfWeekData = useMemo(() => {
    if (filteredPositions.length === 0) return [];

    const dayMap: Record<string, number> = {
      'Sun': 0, 'Mon': 0, 'Tue': 0, 'Wed': 0, 'Thu': 0, 'Fri': 0, 'Sat': 0
    };

    filteredPositions.forEach(p => {
      if (p.closed_at) {
        try {
          const day = format(parseISO(p.closed_at), 'EEE');
          dayMap[day] = (dayMap[day] || 0) + getPnl(p);
        } catch {}
      }
    });

    return ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map(day => ({
      day,
      pnl: dayMap[day] || 0,
    }));
  }, [filteredPositions]);

  const handleTimeRangeChange = (_: React.MouseEvent<HTMLElement>, newRange: TimeRange | null) => {
    if (newRange) {
      setTimeRange(newRange);
    }
  };

  const handleExportClick = (event: React.MouseEvent<HTMLElement>) => {
    setExportAnchorEl(event.currentTarget);
  };

  const handleExportClose = () => {
    setExportAnchorEl(null);
  };

  const toFixed = (val: any, decimals: number): string => {
    if (val === null || val === undefined) return '0.' + '0'.repeat(decimals);
    const num = typeof val === 'string' ? parseFloat(val) : val;
    return typeof num === 'number' && !isNaN(num) ? num.toFixed(decimals) : '0.' + '0'.repeat(decimals);
  };

  const exportToCSV = () => {
    if (filteredPositions.length === 0) return;

    const headers = ['Symbol', 'Side', 'Entry Price', 'Invested USD', 'Realized PnL', 'Created At', 'Closed At'];
    const rows = filteredPositions.map(p => [
      p.symbol,
      p.side,
      toFixed(p.weighted_avg_entry, 4),
      toFixed(p.total_invested_usd, 2),
      toFixed(p.realized_pnl_usd, 2),
      p.created_at ? format(parseISO(p.created_at), 'yyyy-MM-dd HH:mm:ss') : '',
      p.closed_at ? format(parseISO(p.closed_at), 'yyyy-MM-dd HH:mm:ss') : ''
    ]);

    const csvContent = [
      headers.join(','),
      ...rows.map(row => row.join(','))
    ].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.setAttribute('href', url);
    link.setAttribute('download', `trading_analytics_${timeRange}_${format(new Date(), 'yyyyMMdd')}.csv`);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    handleExportClose();
  };

  const exportSummaryToCSV = () => {
    const summaryData = [
      ['Metric', 'Value'],
      ['Time Range', timeRange],
      ['Total Trades', metrics.totalTrades],
      ['Winning Trades', metrics.winningTrades],
      ['Losing Trades', metrics.losingTrades],
      ['Win Rate', `${metrics.winRate.toFixed(2)}%`],
      ['Total PnL', `$${metrics.totalPnl.toFixed(2)}`],
      ['Average Win', `$${metrics.avgWin.toFixed(2)}`],
      ['Average Loss', `$${metrics.avgLoss.toFixed(2)}`],
      ['Profit Factor', metrics.profitFactor === Infinity ? 'Infinity' : metrics.profitFactor.toFixed(2)],
      ['Largest Win', `$${metrics.largestWin.toFixed(2)}`],
      ['Largest Loss', `$${metrics.largestLoss.toFixed(2)}`],
      ['Avg Hold Time (hours)', metrics.avgHoldTime.toFixed(2)],
      [''],
      ['Pair Performance'],
      ['Symbol', 'PnL', 'Trades', 'Win Rate'],
      ...pairPerformance.map(p => [p.symbol, `$${p.pnl.toFixed(2)}`, p.trades, `${p.winRate.toFixed(2)}%`])
    ];

    const csvContent = summaryData.map(row => row.join(',')).join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.setAttribute('href', url);
    link.setAttribute('download', `trading_summary_${timeRange}_${format(new Date(), 'yyyyMMdd')}.csv`);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    handleExportClose();
  };

  const formatCurrency = (value: number) => {
    const prefix = value >= 0 ? '+' : '';
    return `${prefix}$${Math.abs(value).toFixed(2)}`;
  };

  const formatCurrencyPlain = (value: number | string | undefined | null) => {
    const num = safeNumber(value);
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    }).format(num);
  };

  const formatHours = (hours: number) => {
    if (hours < 1) return `${Math.round(hours * 60)}m`;
    if (hours < 24) return `${hours.toFixed(1)}h`;
    return `${(hours / 24).toFixed(1)}d`;
  };

  // Loading skeleton
  if ((loading || dashboardLoading) && positionHistory.length === 0) {
    return (
      <Box sx={{ p: { xs: 2, sm: 3 } }}>
        <Skeleton variant="text" width={200} height={40} sx={{ mb: 3 }} />
        <Grid container spacing={3}>
          {[1, 2, 3, 4].map(i => (
            <Grid key={i} size={{ xs: 6, sm: 3 }}>
              <Skeleton variant="rectangular" height={80} sx={{ borderRadius: 2 }} />
            </Grid>
          ))}
        </Grid>
        <Skeleton variant="rectangular" height={300} sx={{ mt: 3, borderRadius: 2 }} />
      </Box>
    );
  }

  return (
    <Box sx={{ flexGrow: 1, p: { xs: 1.5, sm: 3 }, maxWidth: '100%', overflowX: 'hidden' }}>
      {/* Header */}
      <Box sx={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: { xs: 'flex-start', sm: 'center' },
        flexDirection: { xs: 'column', sm: 'row' },
        gap: { xs: 2, sm: 0 },
        mb: 3
      }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Typography variant="h4" sx={{ fontSize: { xs: '1.5rem', sm: '2.125rem' } }}>
            Analytics
          </Typography>
          <Chip
            label={`${metrics.totalTrades} trades`}
            size="small"
            variant="outlined"
          />
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
          <ToggleButtonGroup
            value={timeRange}
            exclusive
            onChange={handleTimeRangeChange}
            size="small"
          >
            <ToggleButton value="24h" sx={{ px: { xs: 1, sm: 2 } }}>24h</ToggleButton>
            <ToggleButton value="7d" sx={{ px: { xs: 1, sm: 2 } }}>7d</ToggleButton>
            <ToggleButton value="30d" sx={{ px: { xs: 1, sm: 2 } }}>30d</ToggleButton>
            <ToggleButton value="all" sx={{ px: { xs: 1, sm: 2 } }}>All</ToggleButton>
          </ToggleButtonGroup>
          <Button
            variant="outlined"
            size="small"
            startIcon={<DownloadIcon />}
            onClick={handleExportClick}
            disabled={filteredPositions.length === 0}
            sx={{ display: { xs: 'none', sm: 'flex' } }}
          >
            Export
          </Button>
          <Menu
            anchorEl={exportAnchorEl}
            open={exportMenuOpen}
            onClose={handleExportClose}
            anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
            transformOrigin={{ vertical: 'top', horizontal: 'right' }}
          >
            <MenuItem onClick={exportToCSV}>
              <ListItemIcon><TableChartIcon fontSize="small" /></ListItemIcon>
              <ListItemText>Export Trades (CSV)</ListItemText>
            </MenuItem>
            <MenuItem onClick={exportSummaryToCSV}>
              <ListItemIcon><DescriptionIcon fontSize="small" /></ListItemIcon>
              <ListItemText>Export Summary (CSV)</ListItemText>
            </MenuItem>
          </Menu>
          <DataFreshnessIndicator lastUpdated={lastUpdated} />
          <IconButton
            onClick={() => { fetchPositionHistory(); fetchDashboardData(); setLastUpdated(new Date()); }}
            color="primary"
            size="small"
          >
            <RefreshIcon />
          </IconButton>
        </Box>
      </Box>

      {/* PnL Period Summary - Horizontal Bar */}
      {perf && (
        <Card sx={{ mb: 3, bgcolor: 'background.paper' }}>
          <CardContent sx={{ py: 2, px: { xs: 1.5, sm: 2 } }}>
            <Grid container spacing={{ xs: 1, sm: 2 }} alignItems="center">
              <Grid size={{ xs: 6, sm: 3 }}>
                <Typography variant="caption" color="text.secondary">Today</Typography>
                <Typography
                  fontWeight={600}
                  sx={{
                    color: safeNumber(perf.pnl_metrics.pnl_today) >= 0 ? 'success.main' : 'error.main',
                    fontFamily: 'monospace',
                    fontSize: { xs: '0.9rem', sm: '1.25rem' }
                  }}
                >
                  {formatCurrencyPlain(perf.pnl_metrics.pnl_today)}
                </Typography>
              </Grid>
              <Grid size={{ xs: 6, sm: 3 }}>
                <Typography variant="caption" color="text.secondary">This Week</Typography>
                <Typography
                  fontWeight={600}
                  sx={{
                    color: safeNumber(perf.pnl_metrics.pnl_week) >= 0 ? 'success.main' : 'error.main',
                    fontFamily: 'monospace',
                    fontSize: { xs: '0.9rem', sm: '1.25rem' }
                  }}
                >
                  {formatCurrencyPlain(perf.pnl_metrics.pnl_week)}
                </Typography>
              </Grid>
              <Grid size={{ xs: 6, sm: 3 }}>
                <Typography variant="caption" color="text.secondary">This Month</Typography>
                <Typography
                  fontWeight={600}
                  sx={{
                    color: safeNumber(perf.pnl_metrics.pnl_month) >= 0 ? 'success.main' : 'error.main',
                    fontFamily: 'monospace',
                    fontSize: { xs: '0.9rem', sm: '1.25rem' }
                  }}
                >
                  {formatCurrencyPlain(perf.pnl_metrics.pnl_month)}
                </Typography>
              </Grid>
              <Grid size={{ xs: 6, sm: 3 }}>
                <Typography variant="caption" color="text.secondary">All Time</Typography>
                <Typography
                  fontWeight={600}
                  sx={{
                    color: safeNumber(perf.pnl_metrics.pnl_all_time) >= 0 ? 'success.main' : 'error.main',
                    fontFamily: 'monospace',
                    fontSize: { xs: '0.9rem', sm: '1.25rem' }
                  }}
                >
                  {formatCurrencyPlain(perf.pnl_metrics.pnl_all_time)}
                </Typography>
              </Grid>
            </Grid>
          </CardContent>
        </Card>
      )}

      {/* Key Metrics Row */}
      <Grid container spacing={{ xs: 1, sm: 2 }} sx={{ mb: 3 }}>
        <Grid size={{ xs: 6, sm: 3 }}>
          <Card sx={{ height: '100%' }}>
            <CardContent sx={{ py: { xs: 1.5, sm: 2 }, px: { xs: 1.5, sm: 2 } }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.5 }}>
                {metrics.totalPnl >= 0 ? (
                  <TrendingUpIcon sx={{ color: 'success.main', fontSize: { xs: 16, sm: 20 } }} />
                ) : (
                  <TrendingDownIcon sx={{ color: 'error.main', fontSize: { xs: 16, sm: 20 } }} />
                )}
                <Typography variant="caption" color="text.secondary">Total PnL</Typography>
              </Box>
              <Typography
                fontWeight={700}
                sx={{
                  color: metrics.totalPnl >= 0 ? 'success.main' : 'error.main',
                  fontFamily: 'monospace',
                  fontSize: { xs: '1rem', sm: '1.5rem' }
                }}
              >
                {formatCurrency(metrics.totalPnl)}
              </Typography>
              <Typography variant="caption" color="text.secondary" sx={{ fontSize: { xs: '0.65rem', sm: '0.75rem' } }}>
                {metrics.totalTrades} trades in {timeRange}
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid size={{ xs: 6, sm: 3 }}>
          <Card sx={{ height: '100%' }}>
            <CardContent sx={{ py: { xs: 1.5, sm: 2 }, px: { xs: 1.5, sm: 2 } }}>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                Win Rate
              </Typography>
              <Typography fontWeight={700} sx={{ fontSize: { xs: '1rem', sm: '1.5rem' } }}>
                {safeToFixed(metrics.winRate, 1)}%
              </Typography>
              <Box sx={{ display: 'flex', gap: 0.5, mt: 0.5 }}>
                <Chip
                  label={`${metrics.winningTrades}W`}
                  size="small"
                  sx={{ bgcolor: 'success.main', color: 'white', fontSize: { xs: '0.6rem', sm: '0.7rem' }, height: { xs: 18, sm: 20 } }}
                />
                <Chip
                  label={`${metrics.losingTrades}L`}
                  size="small"
                  sx={{ bgcolor: 'error.main', color: 'white', fontSize: { xs: '0.6rem', sm: '0.7rem' }, height: { xs: 18, sm: 20 } }}
                />
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid size={{ xs: 6, sm: 3 }}>
          <Card sx={{ height: '100%' }}>
            <CardContent sx={{ py: { xs: 1.5, sm: 2 }, px: { xs: 1.5, sm: 2 } }}>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                Profit Factor
              </Typography>
              <Typography
                fontWeight={700}
                sx={{ color: metrics.profitFactor >= 1 ? 'success.main' : 'error.main', fontSize: { xs: '1rem', sm: '1.5rem' } }}
              >
                {metrics.profitFactor === Infinity ? '∞' : safeToFixed(metrics.profitFactor)}
              </Typography>
              <Typography variant="caption" color="text.secondary" sx={{ fontSize: { xs: '0.65rem', sm: '0.75rem' } }}>
                {metrics.profitFactor >= 1.5 ? 'Good' : metrics.profitFactor >= 1 ? 'Okay' : 'Poor'}
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid size={{ xs: 6, sm: 3 }}>
          <Card sx={{ height: '100%' }}>
            <CardContent sx={{ py: { xs: 1.5, sm: 2 }, px: { xs: 1.5, sm: 2 } }}>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                Avg Hold Time
              </Typography>
              <Typography fontWeight={700} sx={{ fontSize: { xs: '1rem', sm: '1.5rem' } }}>
                {formatHours(metrics.avgHoldTime)}
              </Typography>
              <Typography variant="caption" color="text.secondary" sx={{ fontSize: { xs: '0.65rem', sm: '0.75rem' } }}>
                per trade
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Equity Curve - Full Width */}
      <Card sx={{ mb: 3 }}>
        <CardContent sx={{ px: { xs: 1.5, sm: 2 } }}>
          <Typography variant="subtitle1" fontWeight={600} gutterBottom>
            Equity Curve
          </Typography>
          {equityCurveData.length > 0 ? (
            <Box sx={{ width: '100%', height: { xs: 250, sm: 300 } }}>
              <ResponsiveContainer>
                <AreaChart data={equityCurveData}>
                  <defs>
                    <linearGradient id="colorCumulative" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                  <XAxis
                    dataKey="trade"
                    tick={{ fill: '#9ca3af', fontSize: 12 }}
                    axisLine={{ stroke: 'rgba(255,255,255,0.1)' }}
                  />
                  <YAxis
                    tick={{ fill: '#9ca3af', fontSize: 12 }}
                    axisLine={{ stroke: 'rgba(255,255,255,0.1)' }}
                    tickFormatter={(value) => `$${value}`}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#1a1f2e',
                      border: '1px solid rgba(255,255,255,0.1)',
                      borderRadius: 8,
                    }}
                    labelFormatter={(label) => `Trade #${label}`}
                    formatter={(value) => [
                      `$${(typeof value === 'number' ? value : 0).toFixed(2)}`,
                      'PnL'
                    ]}
                  />
                  <Area
                    type="monotone"
                    dataKey="cumulative"
                    stroke="#6366f1"
                    strokeWidth={2}
                    fill="url(#colorCumulative)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </Box>
          ) : (
            <Box sx={{ height: 250, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Typography color="text.secondary">No closed trades in selected period</Typography>
            </Box>
          )}
        </CardContent>
      </Card>

      {/* Performance Summary & Best/Worst */}
      <Grid container spacing={{ xs: 2, sm: 3 }} sx={{ mb: 3 }}>
        {/* Performance Summary - Consolidated */}
        <Grid size={{ xs: 12, md: 6 }}>
          <Card sx={{ height: '100%' }}>
            <CardContent sx={{ px: { xs: 1.5, sm: 2 } }}>
              <Typography variant="subtitle1" fontWeight={600} gutterBottom>
                Performance Summary
              </Typography>

              {/* Win/Loss Bar */}
              <Box sx={{ mb: 2 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                  <Typography variant="caption" color="text.secondary">Win/Loss Ratio</Typography>
                  <Typography variant="caption" fontWeight={600}>
                    {metrics.winningTrades}/{metrics.losingTrades}
                  </Typography>
                </Box>
                <LinearProgress
                  variant="determinate"
                  value={metrics.totalTrades > 0 ? (metrics.winningTrades / metrics.totalTrades) * 100 : 0}
                  sx={{
                    height: 8,
                    borderRadius: 4,
                    bgcolor: 'error.dark',
                    '& .MuiLinearProgress-bar': { bgcolor: 'success.main' }
                  }}
                />
              </Box>

              {/* Stats Grid */}
              <Grid container spacing={1}>
                <Grid size={{ xs: 6 }}>
                  <Box sx={{ textAlign: 'center', p: { xs: 1, sm: 1.5 }, bgcolor: 'background.default', borderRadius: 1 }}>
                    <Typography color="success.main" fontWeight={600} sx={{ fontSize: { xs: '0.85rem', sm: '1.1rem' } }}>
                      {formatCurrency(metrics.avgWin)}
                    </Typography>
                    <Typography variant="caption" color="text.secondary" sx={{ fontSize: { xs: '0.65rem', sm: '0.75rem' } }}>Avg Win</Typography>
                  </Box>
                </Grid>
                <Grid size={{ xs: 6 }}>
                  <Box sx={{ textAlign: 'center', p: { xs: 1, sm: 1.5 }, bgcolor: 'background.default', borderRadius: 1 }}>
                    <Typography color="error.main" fontWeight={600} sx={{ fontSize: { xs: '0.85rem', sm: '1.1rem' } }}>
                      -${safeToFixed(metrics.avgLoss)}
                    </Typography>
                    <Typography variant="caption" color="text.secondary" sx={{ fontSize: { xs: '0.65rem', sm: '0.75rem' } }}>Avg Loss</Typography>
                  </Box>
                </Grid>
                <Grid size={{ xs: 6 }}>
                  <Box sx={{ textAlign: 'center', p: { xs: 1, sm: 1.5 }, bgcolor: 'background.default', borderRadius: 1 }}>
                    <Typography color="success.main" fontWeight={600} sx={{ fontSize: { xs: '0.85rem', sm: '1.1rem' } }}>
                      {formatCurrency(metrics.largestWin)}
                    </Typography>
                    <Typography variant="caption" color="text.secondary" sx={{ fontSize: { xs: '0.65rem', sm: '0.75rem' } }}>Best Trade</Typography>
                  </Box>
                </Grid>
                <Grid size={{ xs: 6 }}>
                  <Box sx={{ textAlign: 'center', p: { xs: 1, sm: 1.5 }, bgcolor: 'background.default', borderRadius: 1 }}>
                    <Typography color="error.main" fontWeight={600} sx={{ fontSize: { xs: '0.85rem', sm: '1.1rem' } }}>
                      {formatCurrency(metrics.largestLoss)}
                    </Typography>
                    <Typography variant="caption" color="text.secondary" sx={{ fontSize: { xs: '0.65rem', sm: '0.75rem' } }}>Worst Trade</Typography>
                  </Box>
                </Grid>
              </Grid>

              {/* Risk Metrics from Dashboard */}
              {perf && (
                <Box sx={{ mt: 2, pt: 2, borderTop: '1px solid', borderColor: 'divider' }}>
                  <Typography variant="caption" color="text.secondary" sx={{ mb: 1, display: 'block' }}>
                    Risk Metrics
                  </Typography>
                  <Grid container spacing={1}>
                    <Grid size={{ xs: 4 }}>
                      <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.65rem' }}>Max DD</Typography>
                      <Typography fontWeight={600} color="error.main" sx={{ fontSize: { xs: '0.75rem', sm: '0.875rem' } }}>
                        {formatCurrencyPlain(perf.risk_metrics.max_drawdown)}
                      </Typography>
                    </Grid>
                    <Grid size={{ xs: 4 }}>
                      <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.65rem' }}>Sharpe</Typography>
                      <Typography fontWeight={600} sx={{ fontSize: { xs: '0.75rem', sm: '0.875rem' } }}>
                        {safeToFixed(perf.risk_metrics.sharpe_ratio ?? 0)}
                      </Typography>
                    </Grid>
                    <Grid size={{ xs: 4 }}>
                      <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.65rem' }}>Sortino</Typography>
                      <Typography fontWeight={600} sx={{ fontSize: { xs: '0.75rem', sm: '0.875rem' } }}>
                        {safeToFixed(perf.risk_metrics.sortino_ratio ?? 0)}
                      </Typography>
                    </Grid>
                  </Grid>
                </Box>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Pair Performance Table */}
        <Grid size={{ xs: 12, md: 6 }}>
          <Card sx={{ height: '100%' }}>
            <CardContent sx={{ px: { xs: 1.5, sm: 2 } }}>
              <Typography variant="subtitle1" fontWeight={600} gutterBottom>
                Performance by Pair
              </Typography>
              {pairPerformance.length > 0 ? (
                <Box sx={{ overflowX: 'auto', mx: { xs: -1.5, sm: 0 } }}>
                  <Table size="small" sx={{ minWidth: { xs: 280, sm: 'auto' } }}>
                    <TableHead>
                      <TableRow>
                        <TableCell sx={{ fontSize: { xs: '0.7rem', sm: '0.875rem' }, py: 1 }}>Symbol</TableCell>
                        <TableCell align="center" sx={{ fontSize: { xs: '0.7rem', sm: '0.875rem' }, py: 1 }}>Trades</TableCell>
                        <TableCell align="center" sx={{ fontSize: { xs: '0.7rem', sm: '0.875rem' }, py: 1 }}>WR</TableCell>
                        <TableCell align="right" sx={{ fontSize: { xs: '0.7rem', sm: '0.875rem' }, py: 1 }}>PnL</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {pairPerformance.slice(0, 8).map((pair) => (
                        <TableRow key={pair.symbol} sx={{ '&:last-child td': { border: 0 } }}>
                          <TableCell sx={{ fontWeight: 600, py: 0.75, fontSize: { xs: '0.75rem', sm: '0.875rem' } }}>
                            {pair.symbol}
                          </TableCell>
                          <TableCell align="center" sx={{ py: 0.75, fontSize: { xs: '0.75rem', sm: '0.875rem' } }}>
                            {pair.trades}
                          </TableCell>
                          <TableCell align="center" sx={{ py: 0.75 }}>
                            <Chip
                              label={`${safeToFixed(pair.winRate, 0)}%`}
                              size="small"
                              color={pair.winRate >= 50 ? 'success' : 'error'}
                              sx={{ fontSize: { xs: '0.6rem', sm: '0.7rem' }, height: { xs: 18, sm: 20 } }}
                            />
                          </TableCell>
                          <TableCell align="right" sx={{ py: 0.75 }}>
                            <Typography
                              fontWeight={600}
                              sx={{
                                color: pair.pnl >= 0 ? 'success.main' : 'error.main',
                                fontFamily: 'monospace',
                                fontSize: { xs: '0.75rem', sm: '0.875rem' }
                              }}
                            >
                              {formatCurrency(pair.pnl)}
                            </Typography>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </Box>
              ) : (
                <Box sx={{ height: 200, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <Typography color="text.secondary">No pair data available</Typography>
                </Box>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* PnL by Day of Week */}
      <Card>
        <CardContent sx={{ px: { xs: 1.5, sm: 2 } }}>
          <Typography variant="subtitle1" fontWeight={600} gutterBottom>
            PnL by Day of Week
          </Typography>
          {dayOfWeekData.some(d => d.pnl !== 0) ? (
            <Box sx={{ width: '100%', height: { xs: 200, sm: 250 } }}>
              <ResponsiveContainer>
                <BarChart data={dayOfWeekData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                  <XAxis
                    dataKey="day"
                    tick={{ fill: '#9ca3af', fontSize: 12 }}
                    axisLine={{ stroke: 'rgba(255,255,255,0.1)' }}
                  />
                  <YAxis
                    tick={{ fill: '#9ca3af', fontSize: 12 }}
                    axisLine={{ stroke: 'rgba(255,255,255,0.1)' }}
                    tickFormatter={(value) => `$${value}`}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#1a1f2e',
                      border: '1px solid rgba(255,255,255,0.1)',
                      borderRadius: 8,
                    }}
                    formatter={(value) => [`$${(typeof value === 'number' ? value : 0).toFixed(2)}`, 'PnL']}
                  />
                  <Bar dataKey="pnl" radius={[4, 4, 0, 0]}>
                    {dayOfWeekData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.pnl >= 0 ? '#10b981' : '#ef4444'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </Box>
          ) : (
            <Box sx={{ height: 200, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Typography color="text.secondary">No data available</Typography>
            </Box>
          )}
        </CardContent>
      </Card>
    </Box>
  );
};

export default AnalyticsPage;
