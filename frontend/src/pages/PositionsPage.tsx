import React, { useEffect, useState } from 'react';
import { Box, Typography, Button, Collapse, IconButton } from '@mui/material';
import { DataGrid, GridColDef, GridRenderCellParams } from '@mui/x-data-grid';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import KeyboardArrowUpIcon from '@mui/icons-material/KeyboardArrowUp';
import axios from 'axios';

interface DCAOrder {
  id: string;
  price: number;
  amount: number;
  status: string;
  order_type: string;
}

interface Pyramid {
  id: string;
  entry_price: number;
  status: string;
  dca_orders: DCAOrder[];
}

interface PositionGroup {
  id: string;
  symbol: string;
  side: string;
  status: string;
  pnl: number;
  pyramids: Pyramid[];
}

const PositionsPage: React.FC = () => {
  const [positions, setPositions] = useState<PositionGroup[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedRows, setExpandedRows] = useState<Record<string, boolean>>({});

  const fetchPositions = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await axios.get<PositionGroup[]>(`/api/v1/positions/active`);
      setPositions(response.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to fetch positions');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPositions();
    const interval = setInterval(fetchPositions, 5000); // Poll every 5 seconds
    return () => clearInterval(interval);
  }, []);

  const handleForceClose = async (groupId: string) => {
    if (window.confirm('Are you sure you want to force close this position group?')) {
      try {
        await axios.post(`/api/v1/positions/${groupId}/close`);
        alert('Position close initiated.');
        fetchPositions(); // Refresh positions after action
      } catch (err: any) {
        setError(err.response?.data?.detail || 'Failed to force close position');
        console.error(err);
      }
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
    { field: 'symbol', headerName: 'Symbol', width: 150 },
    { field: 'side', headerName: 'Side', width: 100 },
    { field: 'status', headerName: 'Status', width: 150 },
    {
      field: 'pnl',
      headerName: 'PnL',
      width: 120,
      renderCell: (params: GridRenderCellParams<PositionGroup>) => (
        <Typography color={params.value >= 0 ? 'success.main' : 'error.main'}>
          {params.value !== null ? `$${params.value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : 'N/A'}
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
                        - {dca.order_type} @ ${dca.price.toLocaleString()} Qty: {dca.amount} ({dca.status})
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
