import React from 'react';
import { Box, Typography } from '@mui/material';
import { DataGrid, GridColDef } from '@mui/x-data-grid';
import { useDataStore } from '../store/dataStore';

const columns: GridColDef[] = [
  { field: 'symbol', headerName: 'Symbol', width: 120 },
  { field: 'exchange', headerName: 'Exchange', width: 100 },
  { field: 'direction', headerName: 'Direction', width: 90 },
  { field: 'status', headerName: 'Status', width: 90 },
  { field: 'total_quantity', headerName: 'Quantity', type: 'number', width: 100 },
  { field: 'avg_entry_price', headerName: 'Avg Entry Price', type: 'number', width: 150 },
  {
    field: 'unrealized_pnl_usd',
    headerName: 'Unrealized PnL (USD)',
    type: 'number',
    width: 150,
    renderCell: (params) => (
      <span>{params.value != null ? `$${params.value.toFixed(2)}` : ''}</span>
    ),
  },
  {
    field: 'unrealized_pnl_percent',
    headerName: 'Unrealized PnL (%)',
    type: 'number',
    width: 150,
    renderCell: (params) => (
      <span>{params.value != null ? `${params.value.toFixed(2)}%` : ''}</span>
    ),
  },
  { field: 'created_at', headerName: 'Created At', width: 180 },
  { field: 'updated_at', headerName: 'Updated At', width: 180 },
];

const PositionsPage: React.FC = () => {
  const { positionGroups } = useDataStore();

  return (
    <Box sx={{ height: 600, width: '100%' }}>
      <Typography variant="h4" gutterBottom>
        Positions
      </Typography>
      <DataGrid
        rows={positionGroups}
        columns={columns}
        pageSizeOptions={[5, 10, 20, 100]}
        checkboxSelection
        disableRowSelectionOnClick
      />
    </Box>
  );
};

export default PositionsPage;