import React, { useState } from 'react';
import {
  Box,
  Typography,
  Button,
  Stack,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
} from '@mui/material';
import { DataGrid, GridColDef, GridRenderCellParams } from '@mui/x-data-grid';
import { useDataStore } from '../store/dataStore';

const QueuePage: React.FC = () => {
  const { queuedSignals } = useDataStore();
  const [modalOpen, setModalOpen] = useState(false);
  const [selectedSignal, setSelectedSignal] = useState<any>(null);

  const handleForceAddClick = (signal: any) => {
    setSelectedSignal(signal);
    setModalOpen(true);
  };

  const handleModalClose = () => {
    setModalOpen(false);
    setSelectedSignal(null);
  };

  const handleConfirm = () => {
    // TODO: Implement the actual force add logic
    console.log('Force adding signal:', selectedSignal);
    handleModalClose();
  };

  const columns: GridColDef[] = [
    { field: 'symbol', headerName: 'Symbol', width: 120 },
    { field: 'exchange', headerName: 'Exchange', width: 100 },
    { field: 'direction', headerName: 'Direction', width: 90 },
    { field: 'status', headerName: 'Status', width: 90 },
    { field: 'created_at', headerName: 'Created At', width: 180 },
    {
      field: 'actions',
      headerName: 'Actions',
      width: 200,
      renderCell: (params: GridRenderCellParams) => (
        <Stack direction="row" spacing={1}>
          <Button variant="contained" size="small" color="primary">
            Promote
          </Button>
          <Button
            variant="contained"
            size="small"
            color="secondary"
            onClick={() => handleForceAddClick(params.row)}
          >
            Force Add
          </Button>
        </Stack>
      ),
    },
  ];

  return (
    <Box sx={{ height: 600, width: '100%' }}>
      <Typography variant="h4" gutterBottom>
        Queued Signals
      </Typography>
      <DataGrid
        rows={queuedSignals}
        columns={columns}
        pageSizeOptions={[5, 10, 20, 100]}
        checkboxSelection
        disableRowSelectionOnClick
      />
      <Dialog open={modalOpen} onClose={handleModalClose}>
        <DialogTitle>Confirm Force Add</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Are you sure you want to force add the signal for{' '}
            {selectedSignal?.symbol}? This will override the execution pool
            limit.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleModalClose}>Cancel</Button>
          <Button onClick={handleConfirm} color="primary">
            Confirm
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default QueuePage;