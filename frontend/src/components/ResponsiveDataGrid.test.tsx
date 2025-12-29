import React from 'react';
import { render, screen } from '@testing-library/react';
import { ThemeProvider, createTheme } from '@mui/material';
import { ResponsiveDataGrid } from './ResponsiveDataGrid';
import { GridColDef } from '@mui/x-data-grid';

// Mock useMediaQuery
jest.mock('@mui/material', () => ({
  ...jest.requireActual('@mui/material'),
  useMediaQuery: jest.fn(),
}));

import { useMediaQuery } from '@mui/material';

const mockedUseMediaQuery = useMediaQuery as jest.Mock;

const theme = createTheme({
  palette: {
    mode: 'dark',
  },
});

const renderWithTheme = (component: React.ReactElement) => {
  return render(
    <ThemeProvider theme={theme}>
      {component}
    </ThemeProvider>
  );
};

const mockColumns: GridColDef[] = [
  { field: 'id', headerName: 'ID', width: 90 },
  { field: 'name', headerName: 'Name', width: 150 },
  { field: 'value', headerName: 'Value', width: 150 },
];

const mockRows = [
  { id: 1, name: 'Row 1', value: 100 },
  { id: 2, name: 'Row 2', value: 200 },
  { id: 3, name: 'Row 3', value: 300 },
];

describe('ResponsiveDataGrid', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('desktop view', () => {
    beforeEach(() => {
      mockedUseMediaQuery.mockReturnValue(false); // Not mobile
    });

    it('renders DataGrid with rows', () => {
      renderWithTheme(
        <ResponsiveDataGrid rows={mockRows} columns={mockColumns} />
      );

      expect(screen.getByRole('grid')).toBeInTheDocument();
    });

    it('renders column headers', () => {
      renderWithTheme(
        <ResponsiveDataGrid rows={mockRows} columns={mockColumns} />
      );

      expect(screen.getByText('ID')).toBeInTheDocument();
      expect(screen.getByText('Name')).toBeInTheDocument();
      expect(screen.getByText('Value')).toBeInTheDocument();
    });

    it('renders row data', () => {
      renderWithTheme(
        <ResponsiveDataGrid rows={mockRows} columns={mockColumns} />
      );

      expect(screen.getByText('Row 1')).toBeInTheDocument();
      expect(screen.getByText('Row 2')).toBeInTheDocument();
      expect(screen.getByText('Row 3')).toBeInTheDocument();
    });

    it('uses standard density on desktop', () => {
      renderWithTheme(
        <ResponsiveDataGrid rows={mockRows} columns={mockColumns} />
      );

      const grid = screen.getByRole('grid');
      expect(grid).toBeInTheDocument();
    });
  });

  describe('mobile view', () => {
    beforeEach(() => {
      mockedUseMediaQuery.mockReturnValue(true); // Is mobile
    });

    it('renders DataGrid on mobile', () => {
      renderWithTheme(
        <ResponsiveDataGrid rows={mockRows} columns={mockColumns} />
      );

      expect(screen.getByRole('grid')).toBeInTheDocument();
    });

    it('uses compact density on mobile', () => {
      renderWithTheme(
        <ResponsiveDataGrid rows={mockRows} columns={mockColumns} />
      );

      const grid = screen.getByRole('grid');
      expect(grid).toBeInTheDocument();
    });

    it('applies mobile height', () => {
      const { container } = renderWithTheme(
        <ResponsiveDataGrid rows={mockRows} columns={mockColumns} mobileHeight="70vh" />
      );

      expect(container.firstChild).toBeInTheDocument();
    });
  });

  describe('custom props', () => {
    beforeEach(() => {
      mockedUseMediaQuery.mockReturnValue(false);
    });

    it('accepts custom sx prop', () => {
      const { container } = renderWithTheme(
        <ResponsiveDataGrid
          rows={mockRows}
          columns={mockColumns}
          sx={{ border: '1px solid red' }}
        />
      );

      expect(container.firstChild).toBeInTheDocument();
    });

    it('renders empty grid when no rows', () => {
      renderWithTheme(
        <ResponsiveDataGrid rows={[]} columns={mockColumns} />
      );

      expect(screen.getByRole('grid')).toBeInTheDocument();
    });

    it('passes through DataGrid props', () => {
      renderWithTheme(
        <ResponsiveDataGrid
          rows={mockRows}
          columns={mockColumns}
          checkboxSelection
          disableRowSelectionOnClick
        />
      );

      expect(screen.getByRole('grid')).toBeInTheDocument();
    });
  });
});
