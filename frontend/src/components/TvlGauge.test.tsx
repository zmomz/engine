import React from 'react';
import { render, screen } from '@testing-library/react';
import { ThemeProvider, createTheme } from '@mui/material';
import TvlGauge from './TvlGauge';

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

describe('TvlGauge', () => {
  it('renders title', () => {
    renderWithTheme(<TvlGauge tvl={1000} />);
    expect(screen.getByText('Total Value Locked')).toBeInTheDocument();
  });

  it('displays formatted TVL value', () => {
    renderWithTheme(<TvlGauge tvl={12345} />);
    expect(screen.getByText('$12,345')).toBeInTheDocument();
  });

  it('displays Loading when TVL is null', () => {
    renderWithTheme(<TvlGauge tvl={null} />);
    expect(screen.getByText('Loading...')).toBeInTheDocument();
  });

  it('displays zero TVL correctly', () => {
    renderWithTheme(<TvlGauge tvl={0} />);
    expect(screen.getByText('$0')).toBeInTheDocument();
  });

  it('displays large TVL values with proper formatting', () => {
    renderWithTheme(<TvlGauge tvl={1234567890} />);
    expect(screen.getByText('$1,234,567,890')).toBeInTheDocument();
  });

  it('displays decimal TVL values', () => {
    renderWithTheme(<TvlGauge tvl={1234.56} />);
    expect(screen.getByText('$1,234.56')).toBeInTheDocument();
  });
});
