import React, { useEffect, useState, useMemo } from 'react';
import {
  Box,
  Typography,
  Button,
  Paper,
  Tabs,
  Tab,
  Chip,
  Tooltip,
  Grid,
  useTheme,
  useMediaQuery,
  IconButton
} from '@mui/material';
import { DataGrid, GridColDef, GridRenderCellParams, GridToolbar } from '@mui/x-data-grid';
import RefreshIcon from '@mui/icons-material/Refresh';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import CancelIcon from '@mui/icons-material/Cancel';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import WarningIcon from '@mui/icons-material/Warning';
import useQueueStore from '../store/queueStore';
import useConfirmStore from '../store/confirmStore';
import { format } from 'date-fns';
import { QueuePageSkeleton } from '../components/QueueSkeleton';
import { MetricCard } from '../components/MetricCard';
import { DataFreshnessIndicator } from '../components/DataFreshnessIndicator';
import { PriorityScoreBreakdown } from '../components/PriorityScoreBreakdown';
import { useKeyboardShortcuts } from '../hooks/useKeyboardShortcuts';
import QueueSignalCard from '../components/QueueSignalCard';
import ResponsiveTableWrapper from '../components/ResponsiveTableWrapper';
import { safeToFixed, formatCompactPercent } from '../utils/formatters';

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

const QueuePage: React.FC = () => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  const {
    queuedSignals,
    queueHistory,
    loading,
    error,
    fetchQueuedSignals,
    fetchQueueHistory,
    promoteSignal,
    removeSignal
  } = useQueueStore();

  const [tabValue, setTabValue] = useState(0);
  const [lastUpdated, setLastUpdated] = React.useState<Date | null>(null);

  // Keyboard shortcuts
  useKeyboardShortcuts({
    onRefresh: () => {
      fetchQueuedSignals();
      fetchQueueHistory();
      setLastUpdated(new Date());
    },
  });

  useEffect(() => {
    const fetchData = async () => {
      await Promise.all([
        fetchQueuedSignals(),
        fetchQueueHistory()
      ]);
      setLastUpdated(new Date());
    };
    fetchData();

    // Set up polling for active queue
    const interval = setInterval(() => {
      if (tabValue === 0) {
        fetchQueuedSignals(true);
        setLastUpdated(new Date());
      }
    }, 5000);

    return () => clearInterval(interval);
  }, [fetchQueuedSignals, fetchQueueHistory, tabValue]);

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
    if (newValue === 0) fetchQueuedSignals();
    if (newValue === 1) fetchQueueHistory();
  };

  const handlePromote = async (signalId: string) => {
    const confirmed = await useConfirmStore.getState().requestConfirm({
      title: 'Promote Signal',
      message: 'Are you sure you want to promote this signal immediately? It will bypass some checks.',
      confirmText: 'Promote'
    });
    if (confirmed) {
      await promoteSignal(signalId);
    }
  };

  const handleRemove = async (signalId: string) => {
    const confirmed = await useConfirmStore.getState().requestConfirm({
      title: 'Remove Signal',
      message: 'Are you sure you want to remove this signal from the queue?',
      confirmText: 'Remove',
      cancelText: 'Cancel'
    });
    if (confirmed) {
      await removeSignal(signalId);
    }
  };

  const getPnlColor = (value: number | null) => {
    if (value === null || value === undefined) return 'text.primary';
    return value < 0 ? 'error.main' : 'success.main';
  };

  const formatWaitTime = (queuedAt: string | null) => {
    if (!queuedAt) return '-';
    try {
      const queueTime = new Date(queuedAt);
      const now = new Date();
      const diffMs = now.getTime() - queueTime.getTime();
      const minutes = Math.floor(diffMs / (1000 * 60));
      const hours = Math.floor(minutes / 60);
      if (hours > 0) return `${hours}h ${minutes % 60}m`;
      return `${minutes}m`;
    } catch {
      return '-';
    }
  };

  const getPriorityColor = (score: number) => {
    if (score >= 80) return '#ef4444'; // Red - Very High
    if (score >= 60) return '#f59e0b'; // Amber - High
    if (score >= 40) return '#3b82f6'; // Blue - Medium
    return '#6b7280'; // Gray - Low
  };

  // Calculate metrics for Active tab
  const activeMetrics = useMemo(() => {
    const count = queuedSignals.length;
    const highPriorityCount = queuedSignals.filter(s => s.priority_score >= 60).length;
    const avgScore = count > 0
      ? queuedSignals.reduce((sum, s) => sum + (s.priority_score || 0), 0) / count
      : 0;

    // Calculate average wait time
    let avgWaitMinutes = 0;
    if (count > 0) {
      const now = new Date();
      const totalMinutes = queuedSignals.reduce((sum, s) => {
        try {
          const queueTime = new Date(s.queued_at);
          return sum + (now.getTime() - queueTime.getTime()) / (1000 * 60);
        } catch {
          return sum;
        }
      }, 0);
      avgWaitMinutes = totalMinutes / count;
    }

    return {
      count,
      highPriorityCount,
      avgScore,
      avgWaitMinutes
    };
  }, [queuedSignals]);

  // Calculate metrics for History tab
  const historyMetrics = useMemo(() => {
    const total = queueHistory.length;
    const promoted = queueHistory.filter(s => s.status === 'promoted').length;
    const expired = total - promoted;
    const promotionRate = total > 0 ? (promoted / total) * 100 : 0;

    return {
      total,
      promoted,
      expired,
      promotionRate
    };
  }, [queueHistory]);

  // Queue health status
  const getQueueHealth = () => {
    if (activeMetrics.count === 0) {
      return { label: 'Empty', color: 'success' as const, icon: <CheckCircleIcon sx={{ fontSize: 16 }} /> };
    }
    if (activeMetrics.count <= 3) {
      return { label: 'Healthy', color: 'success' as const, icon: <CheckCircleIcon sx={{ fontSize: 16 }} /> };
    }
    if (activeMetrics.count <= 5) {
      return { label: 'Busy', color: 'warning' as const, icon: <WarningIcon sx={{ fontSize: 16 }} /> };
    }
    return { label: 'Backlog', color: 'error' as const, icon: <CancelIcon sx={{ fontSize: 16 }} /> };
  };

  const queueHealth = getQueueHealth();

  const cellStyle = { fontSize: '0.813rem' };
  const monoStyle = { fontSize: '0.813rem', fontFamily: 'monospace' };

  const activeColumns: GridColDef[] = [
    {
      field: 'priority_indicator',
      headerName: '',
      width: 40,
      sortable: false,
      filterable: false,
      align: 'center',
      renderCell: (params: GridRenderCellParams) => {
        const score = Number(params.row.priority_score);
        const color = getPriorityColor(score);
        return (
          <Box
            sx={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              bgcolor: color,
              boxShadow: `0 0 8px ${color}60`,
              animation: score >= 80 ? 'pulse 2s ease-in-out infinite' : 'none',
              '@keyframes pulse': {
                '0%, 100%': { opacity: 1, transform: 'scale(1)' },
                '50%': { opacity: 0.7, transform: 'scale(1.2)' },
              },
            }}
          />
        );
      }
    },
    {
      field: 'symbol',
      headerName: 'Symbol',
      width: 100,
      renderCell: (params: GridRenderCellParams) => (
        <Typography sx={{ ...cellStyle, fontWeight: 600 }}>{params.value}</Typography>
      )
    },
    {
      field: 'side',
      headerName: 'Side',
      width: 75,
      align: 'center',
      headerAlign: 'center',
      renderCell: (params: GridRenderCellParams) => (
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
      field: 'timeframe',
      headerName: 'TF',
      width: 55,
      align: 'center',
      headerAlign: 'center',
      renderCell: (params: GridRenderCellParams) => (
        <Typography sx={cellStyle}>{params.value}m</Typography>
      )
    },
    {
      field: 'exchange',
      headerName: 'Exchange',
      width: 85,
      renderCell: (params) => (
        <Typography sx={cellStyle}>{params.value}</Typography>
      )
    },
    {
      field: 'priority_score',
      headerName: 'Priority',
      width: 160,
      type: 'number',
      renderCell: (params: GridRenderCellParams) => (
        <PriorityScoreBreakdown
          score={Number(params.value)}
          explanation={params.row.priority_explanation}
          currentLoss={params.row.current_loss_percent}
          replacementCount={params.row.replacement_count}
          queuedAt={params.row.queued_at}
        />
      )
    },
    {
      field: 'queued_at',
      headerName: 'Wait',
      width: 75,
      align: 'center',
      headerAlign: 'center',
      renderCell: (params: GridRenderCellParams) => (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
          <AccessTimeIcon sx={{ fontSize: 14, color: 'text.secondary' }} />
          <Typography sx={cellStyle}>{formatWaitTime(params.value)}</Typography>
        </Box>
      )
    },
    {
      field: 'current_loss_percent',
      headerName: 'Loss',
      width: 65,
      align: 'right',
      headerAlign: 'right',
      renderCell: (params) => (
        <Typography
          sx={{
            ...monoStyle,
            color: getPnlColor(params.value),
            fontWeight: params.value && params.value < 0 ? 600 : 400
          }}
        >
          {formatCompactPercent(params.value)}
        </Typography>
      )
    },
    {
      field: 'replacement_count',
      headerName: 'Repl',
      width: 50,
      align: 'center',
      headerAlign: 'center',
      type: 'number',
      renderCell: (params) => (
        <Typography sx={cellStyle}>{params.value || 0}</Typography>
      )
    },
    {
      field: 'actions',
      headerName: '',
      width: 155,
      sortable: false,
      align: 'center',
      renderCell: (params: GridRenderCellParams) => (
        <Box sx={{ display: 'flex', gap: 0.5 }}>
          <Button
            variant="contained"
            color="primary"
            size="small"
            onClick={() => handlePromote(params.row.id)}
            sx={{ fontSize: '0.75rem', minWidth: 65 }}
          >
            Promote
          </Button>
          <Button
            variant="outlined"
            color="error"
            size="small"
            onClick={() => handleRemove(params.row.id)}
            sx={{ fontSize: '0.75rem', minWidth: 65 }}
          >
            Remove
          </Button>
        </Box>
      ),
    },
  ];

  const historyColumns: GridColDef[] = [
    {
      field: 'symbol',
      headerName: 'Symbol',
      width: 100,
      renderCell: (params: GridRenderCellParams) => (
        <Typography sx={{ ...cellStyle, fontWeight: 600 }}>{params.value}</Typography>
      )
    },
    {
      field: 'side',
      headerName: 'Side',
      width: 75,
      align: 'center',
      headerAlign: 'center',
      renderCell: (params: GridRenderCellParams) => (
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
      field: 'timeframe',
      headerName: 'TF',
      width: 55,
      align: 'center',
      headerAlign: 'center',
      renderCell: (params: GridRenderCellParams) => (
        <Typography sx={cellStyle}>{params.value}m</Typography>
      )
    },
    {
      field: 'exchange',
      headerName: 'Exchange',
      width: 85,
      renderCell: (params) => (
        <Typography sx={cellStyle}>{params.value}</Typography>
      )
    },
    {
      field: 'status',
      headerName: 'Result',
      width: 110,
      align: 'center',
      headerAlign: 'center',
      renderCell: (params) => (
        <Chip
          label={params.value?.toUpperCase()}
          color={params.value === 'promoted' ? 'success' : 'error'}
          size="small"
          icon={params.value === 'promoted' ? <CheckCircleIcon /> : <CancelIcon />}
          sx={{ fontSize: '0.7rem', height: 22 }}
        />
      )
    },
    {
      field: 'priority_score',
      headerName: 'Score',
      width: 65,
      align: 'center',
      headerAlign: 'center',
      renderCell: (params) => (
        <Typography
          sx={{ ...monoStyle, color: getPriorityColor(Number(params.value)), fontWeight: 600 }}
        >
          {safeToFixed(params.value, 0)}
        </Typography>
      )
    },
    {
      field: 'priority_explanation',
      headerName: 'Reason',
      width: 200,
      renderCell: (params) => (
        <Tooltip title={params.value || ''} arrow>
          <Typography
            sx={{
              ...cellStyle,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap'
            }}
          >
            {params.value || '-'}
          </Typography>
        </Tooltip>
      )
    },
    {
      field: 'promoted_at',
      headerName: 'Processed',
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
  if (loading && queuedSignals.length === 0 && queueHistory.length === 0) {
    return <QueuePageSkeleton />;
  }

  return (
    <Box sx={{ flexGrow: 1, p: { xs: 2, sm: 3 }, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
      {/* Header */}
      <Box sx={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        mb: 2,
      }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Typography variant="h4" sx={{ fontSize: { xs: '1.5rem', sm: '2.125rem' } }}>
            Queue
          </Typography>
          <Chip
            icon={queueHealth.icon}
            label={queueHealth.label}
            color={queueHealth.color}
            size="small"
            variant="outlined"
          />
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <DataFreshnessIndicator lastUpdated={lastUpdated} />
          <IconButton
            onClick={() => { fetchQueuedSignals(); fetchQueueHistory(); setLastUpdated(new Date()); }}
            color="primary"
            size="small"
          >
            <RefreshIcon />
          </IconButton>
        </Box>
      </Box>

      {error && <Typography color="error" sx={{ mb: 2 }}>{error}</Typography>}

      {/* Summary Metrics - Tab specific */}
      <Grid container spacing={{ xs: 2, sm: 3 }} sx={{ mb: 3 }}>
        {tabValue === 0 ? (
          // Active Queue Metrics
          <>
            <Grid size={{ xs: 6, sm: 6, md: 3 }}>
              <MetricCard
                label="In Queue"
                value={activeMetrics.count.toString()}
                subtitle={activeMetrics.count > 0 ? `Avg Score: ${safeToFixed(activeMetrics.avgScore, 0)}` : 'Queue empty'}
                icon={<AccessTimeIcon />}
                colorScheme={activeMetrics.count > 5 ? 'bearish' : 'neutral'}
                variant="small"
              />
            </Grid>
            <Grid size={{ xs: 6, sm: 6, md: 3 }}>
              <MetricCard
                label="High Priority"
                value={activeMetrics.highPriorityCount.toString()}
                subtitle="Score ≥ 60"
                icon={<WarningIcon />}
                colorScheme={activeMetrics.highPriorityCount > 0 ? 'bearish' : 'neutral'}
                variant="small"
              />
            </Grid>
            <Grid size={{ xs: 6, sm: 6, md: 3 }}>
              <MetricCard
                label="Avg Wait"
                value={activeMetrics.avgWaitMinutes > 60
                  ? `${safeToFixed(activeMetrics.avgWaitMinutes / 60, 1)}h`
                  : `${safeToFixed(activeMetrics.avgWaitMinutes, 0)}m`}
                subtitle="Time in queue"
                icon={<AccessTimeIcon />}
                colorScheme={activeMetrics.avgWaitMinutes > 30 ? 'bearish' : 'neutral'}
                variant="small"
              />
            </Grid>
            <Grid size={{ xs: 6, sm: 6, md: 3 }}>
              <MetricCard
                label="Promotion Rate"
                value={`${safeToFixed(historyMetrics.promotionRate, 0)}%`}
                subtitle={`${historyMetrics.promoted} promoted`}
                icon={<TrendingUpIcon />}
                colorScheme={historyMetrics.promotionRate >= 70 ? 'bullish' : 'neutral'}
                variant="small"
              />
            </Grid>
          </>
        ) : (
          // History Metrics
          <>
            <Grid size={{ xs: 6, sm: 6, md: 3 }}>
              <MetricCard
                label="Total Processed"
                value={historyMetrics.total.toString()}
                subtitle="All time"
                icon={<AccessTimeIcon />}
                colorScheme="neutral"
                variant="small"
              />
            </Grid>
            <Grid size={{ xs: 6, sm: 6, md: 3 }}>
              <MetricCard
                label="Promoted"
                value={historyMetrics.promoted.toString()}
                subtitle={`${safeToFixed(historyMetrics.promotionRate, 1)}% rate`}
                icon={<CheckCircleIcon />}
                colorScheme="bullish"
                variant="small"
              />
            </Grid>
            <Grid size={{ xs: 6, sm: 6, md: 3 }}>
              <MetricCard
                label="Expired/Removed"
                value={historyMetrics.expired.toString()}
                subtitle={historyMetrics.total > 0 ? `${safeToFixed((historyMetrics.expired / historyMetrics.total) * 100, 1)}% rate` : 'None'}
                icon={<CancelIcon />}
                colorScheme={historyMetrics.expired > 0 ? 'bearish' : 'neutral'}
                variant="small"
              />
            </Grid>
            <Grid size={{ xs: 6, sm: 6, md: 3 }}>
              <MetricCard
                label="Success Rate"
                value={`${safeToFixed(historyMetrics.promotionRate, 0)}%`}
                subtitle="Signals promoted"
                icon={<TrendingUpIcon />}
                colorScheme={historyMetrics.promotionRate >= 70 ? 'bullish' : historyMetrics.promotionRate >= 50 ? 'neutral' : 'bearish'}
                variant="small"
              />
            </Grid>
          </>
        )}
      </Grid>

      <Paper sx={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minHeight: 400 }}>
        <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
          <Tabs
            value={tabValue}
            onChange={handleTabChange}
            aria-label="queue tabs"
            variant="scrollable"
            scrollButtons="auto"
            allowScrollButtonsMobile
          >
            <Tab
              label={`Active (${queuedSignals.length})`}
              sx={{ fontSize: { xs: '0.75rem', sm: '0.875rem' } }}
            />
            <Tab
              label={`History (${queueHistory.length})`}
              sx={{ fontSize: { xs: '0.75rem', sm: '0.875rem' } }}
            />
          </Tabs>
        </Box>

        <Box sx={{ flexGrow: 1, overflow: isMobile ? 'auto' : 'hidden' }}>
          <CustomTabPanel value={tabValue} index={0}>
            {isMobile ? (
              <Box sx={{ p: 2, pt: 1 }}>
                {queuedSignals.length > 0 ? (
                  [...queuedSignals]
                    .sort((a, b) => (b.priority_score || 0) - (a.priority_score || 0))
                    .map((signal) => (
                      <QueueSignalCard
                        key={signal.id}
                        signal={signal}
                        onPromote={handlePromote}
                        onRemove={handleRemove}
                      />
                    ))
                ) : (
                  <Box sx={{ textAlign: 'center', py: 6 }}>
                    <CheckCircleIcon sx={{ fontSize: 48, color: 'success.main', mb: 1 }} />
                    <Typography variant="body1" color="text.secondary">
                      Queue is empty
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      Signals will appear here when received
                    </Typography>
                  </Box>
                )}
              </Box>
            ) : (
              <ResponsiveTableWrapper>
                <DataGrid
                  rows={queuedSignals}
                  columns={activeColumns}
                  getRowId={(row) => row.id}
                  loading={loading}
                  disableRowSelectionOnClick
                  slots={{ toolbar: GridToolbar }}
                  initialState={{
                    sorting: {
                      sortModel: [{ field: 'priority_score', sort: 'desc' }],
                    },
                    pagination: { paginationModel: { pageSize: 10 } },
                  }}
                  pageSizeOptions={[10, 25, 50]}
                />
              </ResponsiveTableWrapper>
            )}
          </CustomTabPanel>

          <CustomTabPanel value={tabValue} index={1}>
            {isMobile ? (
              <Box sx={{ p: 2, pt: 1 }}>
                {queueHistory.length > 0 ? (
                  [...queueHistory]
                    .sort((a, b) => new Date(b.promoted_at || 0).getTime() - new Date(a.promoted_at || 0).getTime())
                    .slice(0, 30)
                    .map((signal) => (
                      <Box
                        key={signal.id}
                        sx={{
                          p: 1.5,
                          mb: 1.5,
                          bgcolor: 'background.paper',
                          borderRadius: 1,
                          borderLeft: 4,
                          borderColor: signal.status === 'promoted' ? 'success.main' : 'error.main',
                        }}
                      >
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.5 }}>
                          <Box>
                            <Typography variant="body2" fontWeight={600}>{signal.symbol}</Typography>
                            <Box sx={{ display: 'flex', gap: 0.5, mt: 0.5 }}>
                              <Chip
                                label={signal.side.toUpperCase()}
                                size="small"
                                color={signal.side === 'long' ? 'success' : 'error'}
                                sx={{ height: 18, fontSize: '0.6rem' }}
                              />
                              <Chip
                                label={signal.timeframe}
                                size="small"
                                variant="outlined"
                                sx={{ height: 18, fontSize: '0.6rem' }}
                              />
                            </Box>
                          </Box>
                          <Box sx={{ textAlign: 'right' }}>
                            <Chip
                              label={signal.status?.toUpperCase()}
                              size="small"
                              color={signal.status === 'promoted' ? 'success' : 'error'}
                              sx={{ height: 20, fontSize: '0.65rem' }}
                            />
                            <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 0.5 }}>
                              {signal.promoted_at ? format(new Date(signal.promoted_at), 'MMM d, HH:mm') : '-'}
                            </Typography>
                          </Box>
                        </Box>
                        {signal.priority_explanation && (
                          <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                            {signal.priority_explanation}
                          </Typography>
                        )}
                      </Box>
                    ))
                ) : (
                  <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'center', py: 4 }}>
                    No queue history
                  </Typography>
                )}
              </Box>
            ) : (
              <ResponsiveTableWrapper>
                <DataGrid
                  rows={queueHistory}
                  columns={historyColumns}
                  getRowId={(row) => row.id}
                  loading={loading}
                  disableRowSelectionOnClick
                  slots={{ toolbar: GridToolbar }}
                  initialState={{
                    sorting: {
                      sortModel: [{ field: 'promoted_at', sort: 'desc' }],
                    },
                    pagination: { paginationModel: { pageSize: 10 } },
                  }}
                  pageSizeOptions={[10, 25, 50]}
                />
              </ResponsiveTableWrapper>
            )}
          </CustomTabPanel>
        </Box>
      </Paper>
    </Box>
  );
};

export default QueuePage;
