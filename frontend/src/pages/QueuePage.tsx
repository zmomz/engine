import React, { useEffect, useState } from 'react';
import { Box, Typography, Button, Paper, Tabs, Tab, Chip, Tooltip, IconButton, Stack } from '@mui/material';
import { DataGrid, GridColDef, GridRenderCellParams, GridToolbar } from '@mui/x-data-grid';
import RefreshIcon from '@mui/icons-material/Refresh';
import useQueueStore from '../store/queueStore';
import useConfigStore from '../store/configStore';
import useConfirmStore from '../store/confirmStore';
import { format } from 'date-fns';

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

  const { settings, fetchSettings } = useConfigStore();
  const [tabValue, setTabValue] = useState(0);

  useEffect(() => {
    fetchQueuedSignals();
    fetchQueueHistory();
    if (!settings) {
      fetchSettings();
    }
    // Set up polling for active queue
    const interval = setInterval(() => {
      if (tabValue === 0) fetchQueuedSignals(true);
    }, 5000);

    return () => clearInterval(interval);
  }, [fetchQueuedSignals, fetchQueueHistory, fetchSettings, tabValue, settings]); // Added dependencies

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

  const formatPercentage = (value: number | string | null) => {
    if (value === null || value === undefined) return '-';
    // Handle potential string numbers from Decimal serialization
    const numValue = typeof value === 'string' ? parseFloat(value) : value;
    if (isNaN(numValue)) return '-';
    return `${numValue.toFixed(2)}%`;
  };

  const getPnlColor = (value: number | null) => {
    if (value === null || value === undefined) return 'text.primary';
    return value < 0 ? 'error.main' : 'success.main';
  };

  const commonColumns: GridColDef[] = [
    { field: 'symbol', headerName: 'Symbol', width: 120, flex: 0.5 },
    {
      field: 'side', headerName: 'Side', width: 80,
      renderCell: (params) => (
        <Chip
          label={params.value.toUpperCase()}
          color={params.value === 'long' ? 'success' : 'error'}
          size="small"
          variant="outlined"
        />
      )
    },
    { field: 'timeframe', headerName: 'TF', width: 70 },
    { field: 'exchange', headerName: 'Exchange', width: 100 },
  ];

  const activeColumns: GridColDef[] = [
    ...commonColumns,
    {
      field: 'priority_score',
      headerName: 'Score',
      width: 130,
      type: 'number',
      renderCell: (params) => (
        <Typography variant="body2" fontWeight="bold">
          {Number(params.value).toFixed(0)}
        </Typography>
      )
    },
    {
      field: 'priority_explanation',
      headerName: 'Priority Reason',
      flex: 1.5,
      minWidth: 250,
      renderCell: (params) => (
        <Tooltip title={params.value || ''} arrow placement="top">
          <Typography variant="body2" sx={{
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            cursor: 'help'
          }}>
            {params.value}
          </Typography>
        </Tooltip>
      )
    },
    {
      field: 'current_loss_percent',
      headerName: 'Current Loss',
      width: 120,
      renderCell: (params) => (
        <Typography color={getPnlColor(params.value)} fontWeight={params.value && params.value < 0 ? 'bold' : 'normal'}>
          {formatPercentage(params.value)}
        </Typography>
      )
    },
    { field: 'replacement_count', headerName: 'Replacements', width: 110, type: 'number' },
    {
      field: 'queued_at',
      headerName: 'Time in Queue',
      width: 150,
      valueFormatter: (params) => {
        if (!params) return '';
        try {
          return format(new Date(params as string), 'HH:mm:ss');
        } catch (e) {
          return params;
        }
      }
    },
    {
      field: 'actions',
      headerName: 'Actions',
      width: 180,
      sortable: false,
      renderCell: (params: GridRenderCellParams) => (
        <Box>
          <Button
            variant="contained"
            color="primary"
            size="small"
            onClick={() => handlePromote(params.row.id)}
            sx={{ mr: 1, fontSize: '0.7rem' }}
          >
            Promote
          </Button>
          <Button
            variant="outlined"
            color="error"
            size="small"
            onClick={() => handleRemove(params.row.id)}
            sx={{ fontSize: '0.7rem' }}
          >
            Remove
          </Button>
        </Box>
      ),
    },
  ];

  const historyColumns: GridColDef[] = [
    ...commonColumns,
    {
      field: 'status',
      headerName: 'Status',
      width: 120,
      renderCell: (params) => {
        const color = params.value === 'promoted' ? 'success' : 'error';
        return <Chip label={params.value.toUpperCase()} color={color} size="small" />;
      }
    },
    {
      field: 'promoted_at',
      headerName: 'Processed At',
      width: 200,
      valueFormatter: (params) => {
        if (!params) return '-';
        try {
          return format(new Date(params as string), 'yyyy-MM-dd HH:mm:ss');
        } catch (e) {
          return params;
        }
      }
    },
    {
      field: 'priority_explanation',
      headerName: 'Reason',
      flex: 1,
      align: 'center',
      headerAlign: 'center',
      renderCell: (params) => (
        <Tooltip title={params.value || ''} arrow>
          <Typography variant="body2" sx={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {params.value}
          </Typography>
        </Tooltip>
      )
    },
  ];

  // Helper to show active rules
  const activeRules = settings?.risk_config?.priority_rules?.priority_order?.filter(
    (rule: string) => (settings?.risk_config?.priority_rules?.priority_rules_enabled as any)?.[rule]
  ) || [];

  return (
    <Box sx={{ flexGrow: 1, p: 3, height: '85vh', display: 'flex', flexDirection: 'column' }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h4">
          Queue Management
        </Typography>
        <Box>
          <IconButton onClick={() => { fetchQueuedSignals(); fetchQueueHistory(); }} color="primary">
            <RefreshIcon />
          </IconButton>
        </Box>
      </Box>

      {/* Active Rules Summary */}
      < Paper variant="outlined" sx={{ p: 2, mb: 2, bgcolor: 'background.default' }}>
        <Stack direction="row" spacing={1} alignItems="center">
          <Typography variant="subtitle2" color="text.secondary">Active Priority Logic:</Typography>
          {activeRules.length > 0 ? activeRules.map((rule: string, index: number) => (
            <Chip
              key={rule}
              label={`${index + 1}. ${rule.replace(/_/g, ' ')}`}
              size="small"
              variant="outlined"
              color="primary"
            />
          )) : <Chip label="No rules enabled (FIFO Fallback)" size="small" color="warning" />}
        </Stack>
      </Paper >

      {error && <Typography color="error" sx={{ mb: 2 }}>{error}</Typography>}

      <Paper sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
          <Tabs value={tabValue} onChange={handleTabChange} aria-label="queue tabs">
            <Tab label={`Active Queue (${queuedSignals.length})`} />
            <Tab label="Queue History" />
          </Tabs>
        </Box>

        <Box sx={{ flexGrow: 1, overflow: 'hidden' }}>
          <CustomTabPanel value={tabValue} index={0}>
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
            />
          </CustomTabPanel>

          <CustomTabPanel value={tabValue} index={1}>
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
              }}
            />
          </CustomTabPanel>
        </Box>
      </Paper>
    </Box >
  );
};

export default QueuePage;
