import React, { useEffect, useState } from 'react';
import { Box, Typography, Button, Collapse, IconButton } from '@mui/material';
import { DataGrid, GridColDef, GridRenderCellParams } from '@mui/x-data-grid';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import KeyboardArrowUpIcon from '@mui/icons-material/KeyboardArrowUp';
import useConfirmStore from '../store/confirmStore';
import usePositionsStore, { PositionGroup } from '../store/positionsStore';

const PositionsPage: React.FC = () => {
  const { positions, loading, error, fetchPositions, closePosition } = usePositionsStore();
  const [expandedRows, setExpandedRows] = useState<Record<string, boolean>>({});

  useEffect(() => {
    fetchPositions();
    // WebSocket updates will handle real-time data, no need for polling interval
  }, [fetchPositions]);

  const handleForceClose = async (groupId: string) => {
    const confirmed = await useConfirmStore.getState().requestConfirm({
        title: 'Force Close Position',
        message: 'Are you sure you want to force close this position group?',
        confirmText: 'Force Close',
        cancelText: 'Cancel'
    });

    if (confirmed) {
        await closePosition(groupId);
    }
  };

  const handleExpandClick = (groupId: string) => {
    setExpandedRows((prev) => ({
      ...prev,
      [groupId]: !prev[groupId],
    }));
  };

  const columns: GridColDef[] = [
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
    { field: 'exchange', headerName: 'Exchange', width: 100 },
    { field: 'symbol', headerName: 'Symbol', width: 120 },
    { field: 'side', headerName: 'Side', width: 80 },
    { field: 'status', headerName: 'Status', width: 120 },
    {
      field: 'weighted_avg_entry',
      headerName: 'Avg Entry',
      width: 120,
      renderCell: (params: GridRenderCellParams<PositionGroup>) => (
        params.value ? `$${Number(params.value).toLocaleString(undefined, { minimumFractionDigits: 2 })}` : '-'
      ),
    },
    {
      field: 'pyramid_count',
      headerName: 'Pyramids',
      width: 100,
      valueGetter: (params: any) => `${params.row.pyramid_count || 0} / ${params.row.max_pyramids || 5}`,
    },
    {
      field: 'filled_dca_legs',
      headerName: 'DCA Progress',
      width: 120,
      valueGetter: (params: any) => `${params.row.filled_dca_legs || 0} / ${params.row.total_dca_legs || 0}`,
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
        <Typography color={(params.value || 0) >= 0 ? 'success.main' : 'error.main'}>
          {params.value != null ? `$${Number(params.value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : 'N/A'}
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

  return (
    <Box sx={{ flexGrow: 1, p: 3 }}>
      <Typography variant="h4" gutterBottom>
        Positions
      </Typography>
      {error && <Typography color="error">Error: {error}</Typography>}
      <div style={{ height: 400, width: '100%' }}>
        <DataGrid
          rows={positions}
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
      {positions.map((position) => (
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
