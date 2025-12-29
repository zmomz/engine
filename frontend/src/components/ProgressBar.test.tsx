import React from 'react';
import { render, screen } from '@testing-library/react';
import { ThemeProvider, createTheme } from '@mui/material';
import { ProgressBar, RiskGauge } from './ProgressBar';

// Create a theme with custom palette for testing
const theme = createTheme({
  palette: {
    mode: 'dark',
    primary: { main: '#1976d2' },
    warning: { main: '#ed6c02' },
    info: { main: '#0288d1' },
    success: { main: '#2e7d32' },
    error: { main: '#d32f2f' },
    // @ts-ignore - Custom palette colors
    bullish: { main: '#4caf50' },
    bearish: { main: '#f44336' },
  },
});

const lightTheme = createTheme({
  palette: {
    mode: 'light',
    primary: { main: '#1976d2' },
    // @ts-ignore
    bullish: { main: '#4caf50' },
    bearish: { main: '#f44336' },
  },
});

const renderWithTheme = (component: React.ReactElement, customTheme = theme) => {
  return render(
    <ThemeProvider theme={customTheme}>
      {component}
    </ThemeProvider>
  );
};

describe('ProgressBar', () => {
  describe('basic rendering', () => {
    it('renders with default props', () => {
      renderWithTheme(<ProgressBar value={50} />);
      expect(screen.getByText('50%')).toBeInTheDocument();
    });

    it('renders with custom label', () => {
      renderWithTheme(<ProgressBar value={50} label="Progress" />);
      expect(screen.getByText('Progress')).toBeInTheDocument();
      expect(screen.getByText('50%')).toBeInTheDocument();
    });

    it('hides label when showLabel is false', () => {
      renderWithTheme(<ProgressBar value={50} showLabel={false} />);
      expect(screen.queryByText('50%')).not.toBeInTheDocument();
    });

    it('caps percentage at 100', () => {
      renderWithTheme(<ProgressBar value={150} max={100} />);
      expect(screen.getByText('100%')).toBeInTheDocument();
    });

    it('calculates percentage correctly with custom max', () => {
      renderWithTheme(<ProgressBar value={25} max={50} />);
      expect(screen.getByText('50%')).toBeInTheDocument();
    });
  });

  describe('color schemes', () => {
    it('renders with success color scheme', () => {
      renderWithTheme(<ProgressBar value={50} colorScheme="success" />);
      expect(screen.getByText('50%')).toBeInTheDocument();
    });

    it('renders with bullish color scheme', () => {
      renderWithTheme(<ProgressBar value={50} colorScheme="bullish" />);
      expect(screen.getByText('50%')).toBeInTheDocument();
    });

    it('renders with error color scheme', () => {
      renderWithTheme(<ProgressBar value={50} colorScheme="error" />);
      expect(screen.getByText('50%')).toBeInTheDocument();
    });

    it('renders with bearish color scheme', () => {
      renderWithTheme(<ProgressBar value={50} colorScheme="bearish" />);
      expect(screen.getByText('50%')).toBeInTheDocument();
    });

    it('renders with warning color scheme', () => {
      renderWithTheme(<ProgressBar value={50} colorScheme="warning" />);
      expect(screen.getByText('50%')).toBeInTheDocument();
    });

    it('renders with info color scheme', () => {
      renderWithTheme(<ProgressBar value={50} colorScheme="info" />);
      expect(screen.getByText('50%')).toBeInTheDocument();
    });

    it('renders with primary color scheme', () => {
      renderWithTheme(<ProgressBar value={50} colorScheme="primary" />);
      expect(screen.getByText('50%')).toBeInTheDocument();
    });
  });

  describe('variants', () => {
    it('renders determinate variant', () => {
      renderWithTheme(<ProgressBar value={50} variant="determinate" />);
      expect(screen.getByText('50%')).toBeInTheDocument();
    });

    it('renders indeterminate variant', () => {
      renderWithTheme(<ProgressBar value={50} variant="indeterminate" />);
      expect(screen.getByText('50%')).toBeInTheDocument();
    });
  });

  describe('height and animation', () => {
    it('renders with custom height', () => {
      renderWithTheme(<ProgressBar value={50} height={20} />);
      expect(screen.getByText('50%')).toBeInTheDocument();
    });

    it('renders with animation disabled', () => {
      renderWithTheme(<ProgressBar value={50} animate={false} />);
      expect(screen.getByText('50%')).toBeInTheDocument();
    });
  });

  describe('light theme', () => {
    it('renders correctly in light mode', () => {
      renderWithTheme(<ProgressBar value={50} colorScheme="success" />, lightTheme);
      expect(screen.getByText('50%')).toBeInTheDocument();
    });
  });
});

describe('RiskGauge', () => {
  describe('basic rendering', () => {
    it('renders with default props', () => {
      renderWithTheme(<RiskGauge value={50} />);
      // These labels are always shown at the bottom
      expect(screen.getAllByText('Low').length).toBeGreaterThan(0);
      expect(screen.getAllByText('Medium').length).toBeGreaterThan(0);
      expect(screen.getAllByText('High').length).toBeGreaterThan(0);
    });

    it('renders with label', () => {
      renderWithTheme(<RiskGauge value={50} label="Risk Level" />);
      expect(screen.getByText('Risk Level')).toBeInTheDocument();
    });

    it('shows value when showValue is true', () => {
      renderWithTheme(<RiskGauge value={25} label="Risk" showValue={true} />);
      expect(screen.getByText('Low (25%)')).toBeInTheDocument();
    });

    it('hides value when showValue is false', () => {
      renderWithTheme(<RiskGauge value={25} label="Risk" showValue={false} />);
      // Should not show the percentage in the label area
      expect(screen.queryByText('Low (25%)')).not.toBeInTheDocument();
    });
  });

  describe('risk levels', () => {
    it('shows Low risk for values below low threshold', () => {
      renderWithTheme(<RiskGauge value={20} label="Risk" />);
      expect(screen.getByText('Low (20%)')).toBeInTheDocument();
    });

    it('shows Medium risk for values between low and medium threshold', () => {
      renderWithTheme(<RiskGauge value={45} label="Risk" />);
      expect(screen.getByText('Medium (45%)')).toBeInTheDocument();
    });

    it('shows High risk for values above medium threshold', () => {
      renderWithTheme(<RiskGauge value={75} label="Risk" />);
      expect(screen.getByText('High (75%)')).toBeInTheDocument();
    });
  });

  describe('custom thresholds', () => {
    it('uses custom thresholds', () => {
      renderWithTheme(
        <RiskGauge
          value={50}
          label="Risk"
          thresholds={{ low: 50, medium: 75, high: 100 }}
        />
      );
      // 50 is exactly at low threshold, should be Low
      expect(screen.getByText('Low (50%)')).toBeInTheDocument();
    });

    it('respects custom max', () => {
      renderWithTheme(<RiskGauge value={100} max={200} label="Risk" />);
      // 100/200 = 50%, should be Medium (default medium threshold is 60)
      expect(screen.getByText('Medium (50%)')).toBeInTheDocument();
    });
  });

  describe('color schemes', () => {
    it('uses success color for low risk', () => {
      renderWithTheme(<RiskGauge value={20} label="Risk" />);
      expect(screen.getByText('Low (20%)')).toBeInTheDocument();
    });

    it('uses warning color for medium risk', () => {
      renderWithTheme(<RiskGauge value={50} label="Risk" />);
      expect(screen.getByText('Medium (50%)')).toBeInTheDocument();
    });

    it('uses error color for high risk', () => {
      renderWithTheme(<RiskGauge value={80} label="Risk" />);
      expect(screen.getByText('High (80%)')).toBeInTheDocument();
    });
  });
});
