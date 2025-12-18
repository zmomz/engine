import React, { useEffect, useState } from 'react';
import { Box, Typography, Button, Collapse, IconButton, Paper, Tabs, Tab, Chip } from '@mui/material';
import { DataGrid, GridColDef, GridRenderCellParams, GridToolbar } from '@mui/x-data-grid';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import KeyboardArrowUpIcon from '@mui/icons-material/KeyboardArrowUp';
import RefreshIcon from '@mui/icons-material/Refresh';
import useConfirmStore from '../store/confirmStore';
import usePositionsStore, { PositionGroup } from '../store/positionsStore';
import { format } from 'date-fns';
import { PositionsPageSkeleton } from '../components/PositionsSkeleton';

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

  useEffect(() => {
    fetchPositions();
    fetchPositionHistory();

    // Set up polling for active positions
    const interval = setInterval(() => {
      if (tabValue === 0) fetchPositions(true);
    }, 5000);

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
      // Refresh history after close
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

  const formatPercentage = (value: number | string | null | undefined) => {
    if (value === null || value === undefined) return '-';
    const numValue = typeof value === 'string' ? parseFloat(value) : value;
    if (isNaN(numValue)) return '-';
    return `${numValue >= 0 ? '+' : ''}${numValue.toFixed(2)}%`;
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

  // Helper to format UUID - show first 8 chars
  const formatGroupId = (id: string) => {
    if (!id) return '-';
    return id.substring(0, 8);
  };

  const activeColumns: GridColDef[] = [
    {
      field: 'expand',
      headerName: '',
      width: 50,
      sortable: false,
      filterable: false,
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
      headerName: 'Group ID',
      width: 100,
      renderCell: (params) => (
        <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.85rem' }}>
          {formatGroupId(params.value)}
        </Typography>
      ),
    },
    { field: 'exchange', headerName: 'Exchange', width: 100 },
    { field: 'symbol', headerName: 'Symbol', width: 120 },
    {
      field: 'side',
      headerName: 'Side',
      width: 80,
      renderCell: (params) => (
        <Chip
          label={params.value?.toUpperCase()}
          color={params.value === 'long' ? 'success' : 'error'}
          size="small"
          variant="outlined"
        />
      )
    },
    { field: 'status', headerName: 'Status', width: 120 },
    {
      field: 'weighted_avg_entry',
      headerName: 'Avg Entry',
      width: 120,
      renderCell: (params: GridRenderCellParams<PositionGroup>) => formatCurrency(params.value),
    },
    {
      field: 'pyramid_count',
      headerName: 'Pyramids',
      width: 100,
      valueGetter: (value: any, row: PositionGroup) => `${row.pyramid_count || 0} / ${row.max_pyramids || 5}`,
    },
    {
      field: 'filled_dca_legs',
      headerName: 'DCA Progress',
      width: 120,
      valueGetter: (value: any, row: PositionGroup) => `${row.filled_dca_legs || 0} / ${row.total_dca_legs || 0}`,
    },
    {
      field: 'risk_timer_expires',
      headerName: 'Risk Timer',
      width: 180,
      renderCell: (params: GridRenderCellParams<PositionGroup>) => {
        if (!params.value) return 'Inactive';
        const expires = new Date(params.value);
        const now = new Date();
        const expired = now > expires;
        return (
          <Typography color={expired ? 'error' : 'warning.main'} variant="body2">
            {expired ? 'Active (Expired)' : `Activates: ${expires.toLocaleTimeString()}`}
          </Typography>
        );
      },
    },
    {
      field: 'unrealized_pnl_usd',
      headerName: 'PnL ($)',
      width: 120,
      renderCell: (params: GridRenderCellParams<PositionGroup>) => (
        <Typography color={getPnlColor(params.value)}>
          {formatCurrency(params.value)}
        </Typography>
      ),
    },
    {
      field: 'actions',
      headerName: 'Actions',
      width: 150,
      renderCell: (params: GridRenderCellParams<PositionGroup>) => (
        <Button
          variant="contained"
          color="warning"
          size="small"
          onClick={() => handleForceClose(params.row.id)}
          disabled={params.row.status === 'CLOSING' || params.row.status === 'CLOSED'}
        >
          Force Close
        </Button>
      ),
    },
  ];

  // Show skeleton on initial load
  if (loading && positions.length === 0 && positionHistory.length === 0) {
    return <PositionsPageSkeleton />;
  }

  const historyColumns: GridColDef[] = [
    {
      field: 'id',
      headerName: 'Group ID',
      width: 100,
      renderCell: (params) => (
        <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.85rem' }}>
          {formatGroupId(params.value)}
        </Typography>
      ),
    },
    { field: 'exchange', headerName: 'Exchange', width: 100 },
    { field: 'symbol', headerName: 'Symbol', width: 120 },
    {
      field: 'side',
      headerName: 'Side',
      width: 80,
      renderCell: (params) => (
        <Chip
          label={params.value?.toUpperCase()}
          color={params.value === 'long' ? 'success' : 'error'}
          size="small"
          variant="outlined"
        />
      )
    },
    { field: 'timeframe', headerName: 'TF', width: 70 },
    {
      field: 'weighted_avg_entry',
      headerName: 'Entry Price',
      width: 130,
      renderCell: (params) => formatCurrency(params.value),
    },
    {
      field: 'pyramid_count',
      headerName: 'Pyramids',
      width: 90,
      valueGetter: (value: any, row: PositionGroup) => row.pyramid_count || 0,
    },
    {
      field: 'total_invested_usd',
      headerName: 'Invested',
      width: 110,
      renderCell: (params) => formatCurrency(params.value),
    },
    {
      field: 'realized_pnl_usd',
      headerName: 'PnL ($)',
      width: 120,
      renderCell: (params) => (
        <Typography
          color={getPnlColor(params.value)}
          fontWeight="bold"
        >
          {formatCurrency(params.value)}
        </Typography>
      ),
    },
    {
      field: 'unrealized_pnl_percent',
      headerName: 'PnL (%)',
      width: 100,
      renderCell: (params) => (
        <Typography color={getPnlColor(params.value)}>
          {formatPercentage(params.value)}
        </Typography>
      ),
    },
    {
      field: 'duration',
      headerName: 'Duration',
      width: 100,
      valueGetter: (value: any, row: PositionGroup) => formatDuration(row.created_at, row.closed_at),
    },
    {
      field: 'closed_at',
      headerName: 'Closed At',
      width: 180,
      renderCell: (params) => {
        if (!params.value) return '-';
        try {
          return format(new Date(params.value), 'yyyy-MM-dd HH:mm:ss');
        } catch {
          return params.value;
        }
      }
    },
  ];

  return (
    <Box sx={{ flexGrow: 1, p: { xs: 2, sm: 3 }, height: '85vh', display: 'flex', flexDirection: 'column' }}>
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
        <Box>
          <IconButton
            onClick={() => { fetchPositions(); fetchPositionHistory(); }}
            color="primary"
            size="medium"
          >
            <RefreshIcon />
          </IconButton>
        </Box>
      </Box>

      {error && <Typography color="error" sx={{ mb: 2 }}>{error}</Typography>}

      <Paper sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
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

        <Box sx={{ flexGrow: 1, overflow: 'hidden' }}>
          <CustomTabPanel value={tabValue} index={0}>
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
              sx={{
                '& .MuiDataGrid-root': {
                  fontSize: { xs: '0.75rem', sm: '0.875rem' },
                },
                '& .MuiDataGrid-columnHeaders': {
                  minHeight: { xs: '40px !important', sm: '56px !important' },
                },
                '& .MuiDataGrid-cell': {
                  padding: { xs: '4px', sm: '8px 16px' },
                },
              }}
            />
          </CustomTabPanel>

          <CustomTabPanel value={tabValue} index={1}>
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
              sx={{
                '& .MuiDataGrid-root': {
                  fontSize: { xs: '0.75rem', sm: '0.875rem' },
                },
                '& .MuiDataGrid-columnHeaders': {
                  minHeight: { xs: '40px !important', sm: '56px !important' },
                },
                '& .MuiDataGrid-cell': {
                  padding: { xs: '4px', sm: '8px 16px' },
                },
              }}
            />
          </CustomTabPanel>
        </Box>
      </Paper>

      {/* Expanded pyramid details for active positions */}
      {tabValue === 0 && positions.map((position) => (
        <Collapse in={expandedRows[position.id]} key={position.id} timeout="auto" unmountOnExit>
          <Box sx={{ margin: 1, ml: 5 }}>
            <Typography variant="h6" gutterBottom component="div">
              Pyramids for {position.symbol} ({position.side})
            </Typography>
            {position.pyramids && position.pyramids.length > 0 ? (
              position.pyramids.map((pyramid) => (
                <Box key={pyramid.id} sx={{ ml: 3, mb: 2, borderLeft: '2px solid grey', pl: 2 }}>
                  <Typography variant="subtitle1">Pyramid Entry: ${pyramid.entry_price.toLocaleString()}</Typography>
                  <Typography variant="body2">Status: {pyramid.status}</Typography>
                  <Typography variant="subtitle2" sx={{ mt: 1 }}>DCA Orders:</Typography>
                  {pyramid.dca_orders && pyramid.dca_orders.length > 0 ? (
                    pyramid.dca_orders.map((dca) => (
                      <Typography key={dca.id} variant="body2" sx={{ ml: 2 }}>
                        - {dca.order_type} @ ${dca.price.toLocaleString()} Qty: {dca.quantity} ({dca.status})
                      </Typography>
                    ))
                  ) : (
                    <Typography variant="body2" sx={{ ml: 2 }}>No DCA orders.</Typography>
                  )}
                </Box>
              ))
            ) : (
              <Typography variant="body2">No pyramids found for this position group.</Typography>
            )}
          </Box>
        </Collapse>
      ))}
    </Box>
  );
};

export default PositionsPage;
