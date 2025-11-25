import React, { useEffect } from 'react';
import { Box, Typography, Button } from '@mui/material';
import { DataGrid, GridColDef, GridRenderCellParams } from '@mui/x-data-grid';
import useQueueStore from '../store/queueStore';
import useConfirmStore from '../store/confirmStore';

const QueuePage: React.FC = () => {
  const { queuedSignals, loading, error, fetchQueuedSignals, promoteSignal, removeSignal } = useQueueStore();

  useEffect(() => {
    fetchQueuedSignals();
    // WebSocket updates will handle real-time data
  }, [fetchQueuedSignals]);

  const handlePromote = async (signalId: string) => {
    const confirmed = await useConfirmStore.getState().requestConfirm({
        title: 'Promote Signal',
        message: 'Are you sure you want to promote this signal?',
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

  const columns: GridColDef[] = [
    { field: 'symbol', headerName: 'Symbol', width: 150 },
    { field: 'side', headerName: 'Side', width: 100 },
    { field: 'signal_type', headerName: 'Type', width: 150 },
    { field: 'priority_score', headerName: 'Priority', type: 'number', width: 120 },
    { field: 'created_at', headerName: 'Received At', width: 200 },
    {
      field: 'actions',
      headerName: 'Actions',
      width: 200,
      renderCell: (params: GridRenderCellParams) => (
        <Box>
          <Button
            variant="contained"
            color="primary"
            size="small"
            onClick={() => handlePromote(params.row.id)}
            sx={{ mr: 1 }}
          >
            Promote
          </Button>
          <Button
            variant="outlined"
            color="error"
            size="small"
            onClick={() => handleRemove(params.row.id)}
          >
            Remove
          </Button>
        </Box>
      ),
    },
  ];

  return (
    <Box sx={{ flexGrow: 1, p: 3 }}>
      <Typography variant="h4" gutterBottom>
        Queued Signals
      </Typography>
      {error && <Typography color="error">Error: {error}</Typography>}
      <div style={{ height: 400, width: '100%' }}>
        <DataGrid
          rows={queuedSignals}
          columns={columns}
          getRowId={(row) => row.id}
          loading={loading}
          pageSizeOptions={[5, 10, 20]}
          initialState={{
            pagination: {
              paginationModel: { pageSize: 10, page: 0 },
            },
          }}
        />
      </div>
    </Box>
  );
};

export default QueuePage;
