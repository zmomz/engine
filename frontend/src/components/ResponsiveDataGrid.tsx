import React from 'react';
import { Box, useMediaQuery, useTheme } from '@mui/material';
import { DataGrid, DataGridProps } from '@mui/x-data-grid';

interface ResponsiveDataGridProps extends DataGridProps {
  mobileHeight?: string | number;
}

export const ResponsiveDataGrid: React.FC<ResponsiveDataGridProps> = ({
  mobileHeight = '60vh',
  sx,
  ...props
}) => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

  return (
    <Box
      sx={{
        height: isMobile ? mobileHeight : '100%',
        width: '100%',
        '& .MuiDataGrid-root': {
          fontSize: { xs: '0.75rem', sm: '0.875rem' },
        },
        '& .MuiDataGrid-columnHeaders': {
          fontSize: { xs: '0.75rem', sm: '0.875rem' },
          minHeight: { xs: '40px !important', sm: '56px !important' },
          maxHeight: { xs: '40px !important', sm: '56px !important' },
        },
        '& .MuiDataGrid-cell': {
          fontSize: { xs: '0.75rem', sm: '0.875rem' },
          padding: { xs: '4px 8px', sm: '8px 16px' },
        },
        '& .MuiDataGrid-row': {
          minHeight: { xs: '40px !important', sm: '52px !important' },
          maxHeight: { xs: 'none !important', sm: '52px !important' },
        },
        '& .MuiDataGrid-toolbarContainer': {
          padding: { xs: '8px', sm: '12px' },
          flexDirection: { xs: 'column', sm: 'row' },
          gap: { xs: 1, sm: 0 },
        },
        '& .MuiButton-root': {
          fontSize: { xs: '0.75rem', sm: '0.875rem' },
          padding: { xs: '4px 8px', sm: '6px 16px' },
        },
        ...sx,
      }}
    >
      <DataGrid
        {...props}
        density={isMobile ? 'compact' : 'standard'}
        pageSizeOptions={isMobile ? [5, 10] : [5, 10, 20, 50]}
      />
    </Box>
  );
};
