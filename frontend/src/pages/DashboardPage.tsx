import React, { useEffect, useState } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Grid,
  Chip,
  Tab,
  Tabs,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  LinearProgress,
  Divider
} from '@mui/material';
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer
} from 'recharts';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import CancelIcon from '@mui/icons-material/Cancel';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import TrendingDownIcon from '@mui/icons-material/TrendingDown';
import useDashboardStore, { startDashboardPolling, stopDashboardPolling } from '../store/dashboardStore';

const DashboardPage: React.FC = () => {
  const { data, loading, error, fetchDashboardData } = useDashboardStore();
  const [activeTab, setActiveTab] = useState(0);

  useEffect(() => {
    fetchDashboardData();
    startDashboardPolling();
    return () => stopDashboardPolling();
  }, [fetchDashboardData]);

  if (loading && !data) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <Box>
          <LinearProgress sx={{ mb: 2 }} />
          <Typography>Loading Dashboard...</Typography>
        </Box>
      </Box>
    );
  }

  if (error && !data) {
    return (
      <Box sx={{ p: 3 }}>
        <Typography color="error">Error: {error}</Typography>
      </Box>
    );
  }

  if (!data) {
    return (
      <Box sx={{ p: 3 }}>
        <Typography>No dashboard data available</Typography>
      </Box>
    );
  }

  const live = data.live_dashboard;
  const perf = data.performance_dashboard;

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    }).format(value);
  };

  const formatPercent = (value: number) => {
    return `${value.toFixed(2)}%`;
  };

  // Prepare charts data
  const equityChartData = perf.equity_curve.map(point => ({
    time: point.timestamp ? new Date(point.timestamp).toLocaleDateString() : 'N/A',
    equity: point.equity
  }));

  const returnsHistogramData = perf.trade_distribution.returns.reduce((acc: any[], ret: number) => {
    const bucket = Math.floor(ret / 10) * 10;
    const existing = acc.find(item => item.range === bucket);
    if (existing) {
      existing.count += 1;
    } else {
      acc.push({ range: bucket, count: 1 });
    }
    return acc;
  }, []).sort((a, b) => a.range - b.range);

  const pnlByPairData = Object.entries(perf.pnl_metrics.pnl_by_pair)
    .map(([pair, pnl]) => ({ pair, pnl }))
    .sort((a, b) => b.pnl - a.pnl)
    .slice(0, 10);

  return (
    <Box sx={{ flexGrow: 1, p: 3 }}>
      <Typography variant="h4" gutterBottom>
        Trading Dashboard
      </Typography>

      <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 3 }}>
        <Tabs value={activeTab} onChange={(_, v) => setActiveTab(v)}>
          <Tab label="Live Dashboard" />
          <Tab label="Performance Analytics" />
        </Tabs>
      </Box>

      {/* LIVE DASHBOARD TAB */}
      {activeTab === 0 && (
        <Grid container spacing={3}>
          {/* Status Banner */}
          <Grid size={{ xs: 12 }}>
            <Card>
              <CardContent>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 2 }}>
                  <Box>
                    <Typography variant="h6">Engine Status</Typography>
                    <Chip
                      label={live.engine_status}
                      color={live.engine_status === 'running' ? 'success' : 'error'}
                      icon={live.engine_status === 'running' ? <CheckCircleIcon /> : <CancelIcon />}
                    />
                  </Box>
                  <Box>
                    <Typography variant="h6">Risk Engine</Typography>
                    <Chip
                      label={live.risk_engine_status}
                      color={live.risk_engine_status === 'active' ? 'success' : 'default'}
                    />
                  </Box>
                  <Box>
                    <Typography variant="body2" color="text.secondary">
                      Last Webhook
                    </Typography>
                    <Typography variant="body1">
                      {live.last_webhook_timestamp
                        ? new Date(live.last_webhook_timestamp).toLocaleString()
                        : 'No signals yet'}
                    </Typography>
                  </Box>
                </Box>
              </CardContent>
            </Card>
          </Grid>

          {/* Key Metrics */}
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <Card>
              <CardContent>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  Total PnL
                </Typography>
                <Typography variant="h4" color={live.total_pnl_usd >= 0 ? 'success.main' : 'error.main'}>
                  {formatCurrency(live.total_pnl_usd)}
                </Typography>
                {live.total_pnl_usd >= 0 ? <TrendingUpIcon color="success" /> : <TrendingDownIcon color="error" />}
              </CardContent>
            </Card>
          </Grid>

          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <Card>
              <CardContent>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  Total Value Locked (TVL)
                </Typography>
                <Typography variant="h4">{formatCurrency(live.tvl)}</Typography>
                <Typography variant="caption" color="text.secondary">
                  Free: {formatCurrency(live.free_usdt)}
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <Card>
              <CardContent>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  Active Position Groups
                </Typography>
                <Typography variant="h4">{live.total_active_position_groups}</Typography>
                <Typography variant="caption" color="text.secondary">
                  Queued: {live.queued_signals_count}
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <Card>
              <CardContent>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  Capital Deployed
                </Typography>
                <Typography variant="h4">
                  {formatPercent(live.tvl > 0 ? ((live.tvl - live.free_usdt) / live.tvl) * 100 : 0)}
                </Typography>
                <LinearProgress
                  variant="determinate"
                  value={live.tvl > 0 ? ((live.tvl - live.free_usdt) / live.tvl) * 100 : 0}
                  sx={{ mt: 1 }}
                />
              </CardContent>
            </Card>
          </Grid>

          {/* TVL Gauge */}
          <Grid size={{ xs: 12, md: 6 }}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Capital Allocation
                </Typography>
                <Box sx={{ display: 'flex', justifyContent: 'space-around', mt: 3 }}>
                  <Box sx={{ textAlign: 'center' }}>
                    <Typography variant="h3" color="primary">
                      {formatCurrency(live.tvl - live.free_usdt)}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Deployed
                    </Typography>
                  </Box>
                  <Divider orientation="vertical" flexItem />
                  <Box sx={{ textAlign: 'center' }}>
                    <Typography variant="h3" color="success.main">
                      {formatCurrency(live.free_usdt)}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Free
                    </Typography>
                  </Box>
                </Box>
              </CardContent>
            </Card>
          </Grid>

          {/* Queued Signals */}
          <Grid size={{ xs: 12, md: 6 }}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Queue Status
                </Typography>
                <Box sx={{ mt: 3 }}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2 }}>
                    <Typography>Active Positions</Typography>
                    <Typography variant="h6">{live.total_active_position_groups}</Typography>
                  </Box>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2 }}>
                    <Typography>Queued Signals</Typography>
                    <Chip label={live.queued_signals_count} color={live.queued_signals_count > 0 ? 'warning' : 'default'} />
                  </Box>
                </Box>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {/* PERFORMANCE DASHBOARD TAB */}
      {activeTab === 1 && (
        <Grid container spacing={3}>
          {/* PnL Summary Cards */}
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <Card>
              <CardContent>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  Today's PnL
                </Typography>
                <Typography variant="h5" color={perf.pnl_metrics.pnl_today >= 0 ? 'success.main' : 'error.main'}>
                  {formatCurrency(perf.pnl_metrics.pnl_today)}
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <Card>
              <CardContent>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  This Week
                </Typography>
                <Typography variant="h5" color={perf.pnl_metrics.pnl_week >= 0 ? 'success.main' : 'error.main'}>
                  {formatCurrency(perf.pnl_metrics.pnl_week)}
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <Card>
              <CardContent>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  This Month
                </Typography>
                <Typography variant="h5" color={perf.pnl_metrics.pnl_month >= 0 ? 'success.main' : 'error.main'}>
                  {formatCurrency(perf.pnl_metrics.pnl_month)}
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <Card>
              <CardContent>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  All Time
                </Typography>
                <Typography variant="h5" color={perf.pnl_metrics.pnl_all_time >= 0 ? 'success.main' : 'error.main'}>
                  {formatCurrency(perf.pnl_metrics.pnl_all_time)}
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          {/* Equity Curve */}
          <Grid size={{ xs: 12 }}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Equity Curve
                </Typography>
                <ResponsiveContainer width="100%" height={300}>
                  <LineChart data={equityChartData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="time" />
                    <YAxis />
                    <Tooltip formatter={(value: number) => formatCurrency(value)} />
                    <Legend />
                    <Line type="monotone" dataKey="equity" stroke="#8884d8" strokeWidth={2} />
                  </LineChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          </Grid>

          {/* Win/Loss Stats */}
          <Grid size={{ xs: 12, md: 6 }}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Win/Loss Statistics
                </Typography>
                <Box sx={{ mt: 2 }}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                    <Typography>Total Trades</Typography>
                    <Typography variant="h6">{perf.win_loss_stats.total_trades}</Typography>
                  </Box>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                    <Typography>Wins</Typography>
                    <Typography variant="h6" color="success.main">{perf.win_loss_stats.wins}</Typography>
                  </Box>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                    <Typography>Losses</Typography>
                    <Typography variant="h6" color="error.main">{perf.win_loss_stats.losses}</Typography>
                  </Box>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                    <Typography>Win Rate</Typography>
                    <Typography variant="h6">{formatPercent(perf.win_loss_stats.win_rate)}</Typography>
                  </Box>
                  <Divider sx={{ my: 2 }} />
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                    <Typography>Avg Win</Typography>
                    <Typography color="success.main">{formatCurrency(perf.win_loss_stats.avg_win)}</Typography>
                  </Box>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                    <Typography>Avg Loss</Typography>
                    <Typography color="error.main">{formatCurrency(perf.win_loss_stats.avg_loss)}</Typography>
                  </Box>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                    <Typography>Risk/Reward Ratio</Typography>
                    <Typography variant="h6">{perf.win_loss_stats.rr_ratio.toFixed(2)}</Typography>
                  </Box>
                </Box>
              </CardContent>
            </Card>
          </Grid>

          {/* Risk Metrics */}
          <Grid size={{ xs: 12, md: 6 }}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Risk Metrics
                </Typography>
                <Box sx={{ mt: 2 }}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                    <Typography>Max Drawdown</Typography>
                    <Typography variant="h6" color="error.main">
                      {formatCurrency(perf.risk_metrics.max_drawdown)}
                    </Typography>
                  </Box>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                    <Typography>Current Drawdown</Typography>
                    <Typography color="error.main">
                      {formatCurrency(perf.risk_metrics.current_drawdown)}
                    </Typography>
                  </Box>
                  <Divider sx={{ my: 2 }} />
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                    <Typography>Sharpe Ratio</Typography>
                    <Typography variant="h6">{perf.risk_metrics.sharpe_ratio.toFixed(2)}</Typography>
                  </Box>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                    <Typography>Sortino Ratio</Typography>
                    <Typography variant="h6">{perf.risk_metrics.sortino_ratio.toFixed(2)}</Typography>
                  </Box>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                    <Typography>Profit Factor</Typography>
                    <Typography variant="h6">{perf.risk_metrics.profit_factor.toFixed(2)}</Typography>
                  </Box>
                </Box>
              </CardContent>
            </Card>
          </Grid>

          {/* Returns Histogram */}
          <Grid size={{ xs: 12, md: 6 }}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Trade Returns Distribution
                </Typography>
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={returnsHistogramData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="range" label={{ value: 'PnL Range ($)', position: 'insideBottom', offset: -5 }} />
                    <YAxis label={{ value: 'Count', angle: -90, position: 'insideLeft' }} />
                    <Tooltip />
                    <Bar dataKey="count" fill="#8884d8" />
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          </Grid>

          {/* PnL by Pair */}
          <Grid size={{ xs: 12, md: 6 }}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  PnL by Pair (Top 10)
                </Typography>
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={pnlByPairData} layout="vertical">
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis type="number" />
                    <YAxis dataKey="pair" type="category" width={100} />
                    <Tooltip formatter={(value: number) => formatCurrency(value)} />
                    <Bar dataKey="pnl" fill="#82ca9d" />
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          </Grid>

          {/* Best & Worst Trades */}
          <Grid size={{ xs: 12, md: 6 }}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Best Trades
                </Typography>
                <TableContainer>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Symbol</TableCell>
                        <TableCell align="right">PnL</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {perf.trade_distribution.best_trades.slice(0, 5).map((trade, idx) => (
                        <TableRow key={idx}>
                          <TableCell>{trade[0]}</TableCell>
                          <TableCell align="right" sx={{ color: 'success.main' }}>
                            {formatCurrency(trade[1])}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              </CardContent>
            </Card>
          </Grid>

          <Grid size={{ xs: 12, md: 6 }}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Worst Trades
                </Typography>
                <TableContainer>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Symbol</TableCell>
                        <TableCell align="right">PnL</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {perf.trade_distribution.worst_trades.slice(0, 5).map((trade, idx) => (
                        <TableRow key={idx}>
                          <TableCell>{trade[0]}</TableCell>
                          <TableCell align="right" sx={{ color: 'error.main' }}>
                            {formatCurrency(trade[1])}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}
    </Box>
  );
};

export default DashboardPage;
