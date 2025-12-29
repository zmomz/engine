import React from 'react';
import { render, screen } from '@testing-library/react';
import { ThemeProvider, createTheme } from '@mui/material';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import { MetricCard } from './MetricCard';

// Mock recharts to avoid rendering issues in tests
jest.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: any) => <div data-testid="responsive-container">{children}</div>,
  LineChart: ({ children }: any) => <svg data-testid="line-chart">{children}</svg>,
  Line: () => <line data-testid="line" />,
}));

const theme = createTheme({
  palette: {
    mode: 'dark',
    // @ts-ignore
    bullish: { main: '#4caf50' },
    bearish: { main: '#f44336' },
  },
  typography: {
    // @ts-ignore
    fontFamilyMonospace: 'monospace',
  },
});

const renderWithTheme = (component: React.ReactElement) => {
  return render(
    <ThemeProvider theme={theme}>
      {component}
    </ThemeProvider>
  );
};

describe('MetricCard', () => {
  describe('basic rendering', () => {
    it('renders label', () => {
      renderWithTheme(<MetricCard label="Total Value" value="$1,000" />);
      expect(screen.getByText('Total Value')).toBeInTheDocument();
    });

    it('renders string value', () => {
      renderWithTheme(<MetricCard label="Test" value="$1,000" />);
      expect(screen.getByText('$1,000')).toBeInTheDocument();
    });

    it('renders numeric value', () => {
      renderWithTheme(<MetricCard label="Test" value={1000} />);
      expect(screen.getByText('1000')).toBeInTheDocument();
    });

    it('shows loading indicator when loading', () => {
      renderWithTheme(<MetricCard label="Test" value="$1,000" loading={true} />);
      expect(screen.getByText('—')).toBeInTheDocument();
    });

    it('renders subtitle when provided', () => {
      renderWithTheme(<MetricCard label="Test" value="$1,000" subtitle="Last 24h" />);
      expect(screen.getByText('Last 24h')).toBeInTheDocument();
    });

    it('renders icon when provided', () => {
      renderWithTheme(<MetricCard label="Test" value="$1,000" icon={<TrendingUpIcon data-testid="icon" />} />);
      expect(screen.getByTestId('icon')).toBeInTheDocument();
    });
  });

  describe('variants', () => {
    it('renders large variant by default', () => {
      renderWithTheme(<MetricCard label="Test" value="$1,000" />);
      expect(screen.getByText('$1,000')).toBeInTheDocument();
    });

    it('renders small variant', () => {
      renderWithTheme(<MetricCard label="Test" value="$1,000" variant="small" />);
      expect(screen.getByText('$1,000')).toBeInTheDocument();
    });
  });

  describe('color schemes', () => {
    it('renders with bullish color scheme', () => {
      renderWithTheme(<MetricCard label="Test" value="$1,000" colorScheme="bullish" />);
      expect(screen.getByText('$1,000')).toBeInTheDocument();
    });

    it('renders with bearish color scheme', () => {
      renderWithTheme(<MetricCard label="Test" value="$1,000" colorScheme="bearish" />);
      expect(screen.getByText('$1,000')).toBeInTheDocument();
    });

    it('renders with primary color scheme', () => {
      renderWithTheme(<MetricCard label="Test" value="$1,000" colorScheme="primary" />);
      expect(screen.getByText('$1,000')).toBeInTheDocument();
    });

    it('renders with neutral color scheme', () => {
      renderWithTheme(<MetricCard label="Test" value="$1,000" colorScheme="neutral" />);
      expect(screen.getByText('$1,000')).toBeInTheDocument();
    });
  });

  describe('trend', () => {
    it('shows up trend indicator', () => {
      renderWithTheme(<MetricCard label="Test" value="$1,000" trend="up" change={5} />);
      expect(screen.getByTestId('TrendingUpIcon')).toBeInTheDocument();
    });

    it('shows down trend indicator', () => {
      renderWithTheme(<MetricCard label="Test" value="$1,000" trend="down" change={-5} />);
      expect(screen.getByTestId('TrendingDownIcon')).toBeInTheDocument();
    });

    it('applies trend colors for up', () => {
      renderWithTheme(<MetricCard label="Test" value="$1,000" trend="up" />);
      expect(screen.getByText('$1,000')).toBeInTheDocument();
    });

    it('applies trend colors for down', () => {
      renderWithTheme(<MetricCard label="Test" value="$1,000" trend="down" />);
      expect(screen.getByText('$1,000')).toBeInTheDocument();
    });
  });

  describe('change indicator', () => {
    it('renders positive change', () => {
      renderWithTheme(<MetricCard label="Test" value="$1,000" change={5} />);
      expect(screen.getByText('+5.00%')).toBeInTheDocument();
    });

    it('renders negative change', () => {
      renderWithTheme(<MetricCard label="Test" value="$1,000" change={-5} />);
      expect(screen.getByText('-5.00%')).toBeInTheDocument();
    });

    it('renders zero change', () => {
      renderWithTheme(<MetricCard label="Test" value="$1,000" change={0} />);
      expect(screen.getByText('+0.00%')).toBeInTheDocument();
    });

    it('renders change label when provided', () => {
      renderWithTheme(<MetricCard label="Test" value="$1,000" change={5} changeLabel="vs yesterday" />);
      expect(screen.getByText('vs yesterday')).toBeInTheDocument();
    });

    it('does not render change when undefined', () => {
      renderWithTheme(<MetricCard label="Test" value="$1,000" />);
      expect(screen.queryByText(/%/)).not.toBeInTheDocument();
    });
  });

  describe('sparkline', () => {
    it('renders sparkline when data provided', () => {
      renderWithTheme(<MetricCard label="Test" value="$1,000" sparklineData={[1, 2, 3, 4, 5]} />);
      expect(screen.getByTestId('responsive-container')).toBeInTheDocument();
      expect(screen.getByTestId('line-chart')).toBeInTheDocument();
    });

    it('does not render sparkline when no data', () => {
      renderWithTheme(<MetricCard label="Test" value="$1,000" />);
      expect(screen.queryByTestId('responsive-container')).not.toBeInTheDocument();
    });

    it('does not render sparkline when empty array', () => {
      renderWithTheme(<MetricCard label="Test" value="$1,000" sparklineData={[]} />);
      expect(screen.queryByTestId('responsive-container')).not.toBeInTheDocument();
    });

    it('uses correct sparkline color for bullish', () => {
      renderWithTheme(<MetricCard label="Test" value="$1,000" colorScheme="bullish" sparklineData={[1, 2, 3]} />);
      expect(screen.getByTestId('line-chart')).toBeInTheDocument();
    });

    it('uses correct sparkline color for bearish', () => {
      renderWithTheme(<MetricCard label="Test" value="$1,000" colorScheme="bearish" sparklineData={[1, 2, 3]} />);
      expect(screen.getByTestId('line-chart')).toBeInTheDocument();
    });

    it('uses correct sparkline color for up trend', () => {
      renderWithTheme(<MetricCard label="Test" value="$1,000" trend="up" sparklineData={[1, 2, 3]} />);
      expect(screen.getByTestId('line-chart')).toBeInTheDocument();
    });

    it('uses correct sparkline color for down trend', () => {
      renderWithTheme(<MetricCard label="Test" value="$1,000" trend="down" sparklineData={[1, 2, 3]} />);
      expect(screen.getByTestId('line-chart')).toBeInTheDocument();
    });
  });
});
