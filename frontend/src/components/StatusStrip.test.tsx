import React from 'react';
import { render, screen } from '@testing-library/react';
import { ThemeProvider, createTheme } from '@mui/material';
import { StatusStrip, StatusItem } from './StatusStrip';

// Create a theme for testing
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

describe('StatusStrip', () => {
  const mockItems: StatusItem[] = [
    { label: 'Engine', status: 'success', value: 'Running' },
    { label: 'Risk', status: 'warning', pulsing: true },
    { label: 'API', status: 'error' },
    { label: 'Info', status: 'info', value: 'Active' },
  ];

  it('renders all status items', () => {
    renderWithTheme(<StatusStrip items={mockItems} />);

    expect(screen.getByText('Engine')).toBeInTheDocument();
    expect(screen.getByText('Risk')).toBeInTheDocument();
    expect(screen.getByText('API')).toBeInTheDocument();
    expect(screen.getByText('Info')).toBeInTheDocument();
  });

  it('renders value chips when provided', () => {
    renderWithTheme(<StatusStrip items={mockItems} />);

    expect(screen.getByText('Running')).toBeInTheDocument();
    expect(screen.getByText('Active')).toBeInTheDocument();
  });

  it('does not render chip for items without value', () => {
    const itemsWithoutValue: StatusItem[] = [
      { label: 'Test', status: 'success' },
    ];
    renderWithTheme(<StatusStrip items={itemsWithoutValue} />);

    expect(screen.getByText('Test')).toBeInTheDocument();
    // Only the label should be rendered, no chip
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });

  it('renders empty strip when no items', () => {
    const { container } = renderWithTheme(<StatusStrip items={[]} />);

    // Container should exist but have no status items
    expect(container.querySelector('.MuiBox-root')).toBeInTheDocument();
  });

  it('handles success status', () => {
    const items: StatusItem[] = [{ label: 'Success', status: 'success' }];
    renderWithTheme(<StatusStrip items={items} />);

    expect(screen.getByText('Success')).toBeInTheDocument();
  });

  it('handles warning status', () => {
    const items: StatusItem[] = [{ label: 'Warning', status: 'warning' }];
    renderWithTheme(<StatusStrip items={items} />);

    expect(screen.getByText('Warning')).toBeInTheDocument();
  });

  it('handles error status', () => {
    const items: StatusItem[] = [{ label: 'Error', status: 'error' }];
    renderWithTheme(<StatusStrip items={items} />);

    expect(screen.getByText('Error')).toBeInTheDocument();
  });

  it('handles info status', () => {
    const items: StatusItem[] = [{ label: 'Info', status: 'info' }];
    renderWithTheme(<StatusStrip items={items} />);

    expect(screen.getByText('Info')).toBeInTheDocument();
  });

  it('handles pulsing items', () => {
    const items: StatusItem[] = [{ label: 'Pulsing', status: 'success', pulsing: true }];
    renderWithTheme(<StatusStrip items={items} />);

    expect(screen.getByText('Pulsing')).toBeInTheDocument();
  });

  it('handles non-pulsing items', () => {
    const items: StatusItem[] = [{ label: 'NotPulsing', status: 'success', pulsing: false }];
    renderWithTheme(<StatusStrip items={items} />);

    expect(screen.getByText('NotPulsing')).toBeInTheDocument();
  });
});
