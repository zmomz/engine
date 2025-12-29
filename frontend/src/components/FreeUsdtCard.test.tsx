import React from 'react';
import { render, screen } from '@testing-library/react';
import { ThemeProvider, createTheme } from '@mui/material';
import FreeUsdtCard from './FreeUsdtCard';

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

describe('FreeUsdtCard', () => {
  describe('rendering', () => {
    it('renders title', () => {
      renderWithTheme(<FreeUsdtCard freeUsdt={1000} />);
      expect(screen.getByText('Free USDT')).toBeInTheDocument();
    });

    it('renders formatted amount when provided', () => {
      renderWithTheme(<FreeUsdtCard freeUsdt={1234.56} />);
      // toLocaleString formats with commas
      expect(screen.getByText(/\$1.*234\.56/)).toBeInTheDocument();
    });

    it('renders zero amount', () => {
      renderWithTheme(<FreeUsdtCard freeUsdt={0} />);
      expect(screen.getByText('$0.00')).toBeInTheDocument();
    });

    it('renders Loading... when freeUsdt is null', () => {
      renderWithTheme(<FreeUsdtCard freeUsdt={null} />);
      expect(screen.getByText('Loading...')).toBeInTheDocument();
    });

    it('formats large numbers with commas', () => {
      renderWithTheme(<FreeUsdtCard freeUsdt={1000000} />);
      expect(screen.getByText(/\$1.*000.*000\.00/)).toBeInTheDocument();
    });

    it('rounds to 2 decimal places', () => {
      renderWithTheme(<FreeUsdtCard freeUsdt={99.999} />);
      // Should show 100.00 due to rounding
      expect(screen.getByText('$100.00')).toBeInTheDocument();
    });
  });
});
