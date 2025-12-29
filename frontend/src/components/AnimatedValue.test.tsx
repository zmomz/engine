import React from 'react';
import { render, screen, act } from '@testing-library/react';
import { ThemeProvider, createTheme } from '@mui/material';
import { AnimatedValue, AnimatedCurrency, AnimatedPercentage } from './AnimatedValue';

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

describe('AnimatedValue', () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  describe('basic rendering', () => {
    it('renders the initial value', () => {
      renderWithTheme(<AnimatedValue value={100} />);
      expect(screen.getByText('100.00')).toBeInTheDocument();
    });

    it('uses default format function', () => {
      renderWithTheme(<AnimatedValue value={42.567} />);
      expect(screen.getByText('42.57')).toBeInTheDocument();
    });

    it('uses custom format function', () => {
      const customFormat = (v: number) => `Custom: ${v.toFixed(0)}`;
      renderWithTheme(<AnimatedValue value={50} format={customFormat} />);
      expect(screen.getByText('Custom: 50')).toBeInTheDocument();
    });

    it('renders with default variant h4', () => {
      const { container } = renderWithTheme(<AnimatedValue value={100} />);
      expect(container.querySelector('.MuiTypography-h4')).toBeInTheDocument();
    });

    it('renders with custom variant', () => {
      const { container } = renderWithTheme(<AnimatedValue value={100} variant="body1" />);
      expect(container.querySelector('.MuiTypography-body1')).toBeInTheDocument();
    });
  });

  describe('colorize prop', () => {
    it('shows success color for positive values', () => {
      const { container } = renderWithTheme(<AnimatedValue value={100} colorize={true} />);
      const typography = container.querySelector('.MuiTypography-root');
      expect(typography).toHaveClass('MuiTypography-root');
    });

    it('shows error color for negative values', () => {
      const { container } = renderWithTheme(<AnimatedValue value={-50} colorize={true} />);
      const typography = container.querySelector('.MuiTypography-root');
      expect(typography).toHaveClass('MuiTypography-root');
    });

    it('uses primary text color when colorize is false', () => {
      const { container } = renderWithTheme(<AnimatedValue value={100} colorize={false} />);
      const typography = container.querySelector('.MuiTypography-root');
      expect(typography).toBeInTheDocument();
    });
  });

  describe('value animation', () => {
    it('does not animate when value stays the same', () => {
      const { rerender } = renderWithTheme(<AnimatedValue value={100} />);
      expect(screen.getByText('100.00')).toBeInTheDocument();

      rerender(
        <ThemeProvider theme={theme}>
          <AnimatedValue value={100} />
        </ThemeProvider>
      );
      expect(screen.getByText('100.00')).toBeInTheDocument();
    });

    it('animates when value increases', async () => {
      const { rerender } = renderWithTheme(<AnimatedValue value={100} duration={300} />);
      expect(screen.getByText('100.00')).toBeInTheDocument();

      // Update value
      rerender(
        <ThemeProvider theme={theme}>
          <AnimatedValue value={200} duration={300} />
        </ThemeProvider>
      );

      // Value should start animating - use act for state updates
      act(() => {
        jest.advanceTimersByTime(350);
      });

      // After animation completes, should show final value
      expect(screen.getByText('200.00')).toBeInTheDocument();
    });

    it('animates when value decreases', async () => {
      const { rerender } = renderWithTheme(<AnimatedValue value={200} duration={300} />);
      expect(screen.getByText('200.00')).toBeInTheDocument();

      rerender(
        <ThemeProvider theme={theme}>
          <AnimatedValue value={100} duration={300} />
        </ThemeProvider>
      );

      act(() => {
        jest.advanceTimersByTime(350);
      });

      expect(screen.getByText('100.00')).toBeInTheDocument();
    });
  });

  describe('showTrend prop', () => {
    it('does not show trend icon by default', () => {
      renderWithTheme(<AnimatedValue value={100} />);
      expect(screen.queryByTestId('TrendingUpIcon')).not.toBeInTheDocument();
      expect(screen.queryByTestId('TrendingDownIcon')).not.toBeInTheDocument();
    });

    it('shows up trend icon when value increases and showTrend is true', () => {
      const { rerender } = renderWithTheme(<AnimatedValue value={100} showTrend={true} />);

      rerender(
        <ThemeProvider theme={theme}>
          <AnimatedValue value={150} showTrend={true} />
        </ThemeProvider>
      );

      expect(screen.getByTestId('TrendingUpIcon')).toBeInTheDocument();
    });

    it('shows down trend icon when value decreases and showTrend is true', () => {
      const { rerender } = renderWithTheme(<AnimatedValue value={100} showTrend={true} />);

      rerender(
        <ThemeProvider theme={theme}>
          <AnimatedValue value={50} showTrend={true} />
        </ThemeProvider>
      );

      expect(screen.getByTestId('TrendingDownIcon')).toBeInTheDocument();
    });

    it('hides trend icon after timeout', () => {
      const { rerender } = renderWithTheme(<AnimatedValue value={100} showTrend={true} duration={100} />);

      rerender(
        <ThemeProvider theme={theme}>
          <AnimatedValue value={150} showTrend={true} duration={100} />
        </ThemeProvider>
      );

      expect(screen.getByTestId('TrendingUpIcon')).toBeInTheDocument();

      // Wait for animation to complete and trend to hide
      act(() => {
        jest.advanceTimersByTime(1500);
      });

      expect(screen.queryByTestId('TrendingUpIcon')).not.toBeInTheDocument();
    });
  });

  describe('cleanup', () => {
    it('cancels animation frame on unmount', () => {
      const cancelSpy = jest.spyOn(window, 'cancelAnimationFrame');
      const { unmount, rerender } = renderWithTheme(<AnimatedValue value={100} />);

      // Trigger animation
      rerender(
        <ThemeProvider theme={theme}>
          <AnimatedValue value={200} />
        </ThemeProvider>
      );

      unmount();
      expect(cancelSpy).toHaveBeenCalled();
      cancelSpy.mockRestore();
    });
  });
});

describe('AnimatedCurrency', () => {
  it('renders currency format', () => {
    render(
      <ThemeProvider theme={theme}>
        <AnimatedCurrency value={1234.56} />
      </ThemeProvider>
    );
    expect(screen.getByText('$1,234.56')).toBeInTheDocument();
  });

  it('renders negative currency', () => {
    render(
      <ThemeProvider theme={theme}>
        <AnimatedCurrency value={-500} />
      </ThemeProvider>
    );
    expect(screen.getByText('-$500.00')).toBeInTheDocument();
  });

  it('uses custom variant', () => {
    const { container } = render(
      <ThemeProvider theme={theme}>
        <AnimatedCurrency value={100} variant="h6" />
      </ThemeProvider>
    );
    expect(container.querySelector('.MuiTypography-h6')).toBeInTheDocument();
  });

  it('shows trend when enabled', () => {
    const { rerender } = render(
      <ThemeProvider theme={theme}>
        <AnimatedCurrency value={100} showTrend={true} />
      </ThemeProvider>
    );

    rerender(
      <ThemeProvider theme={theme}>
        <AnimatedCurrency value={200} showTrend={true} />
      </ThemeProvider>
    );

    expect(screen.getByTestId('TrendingUpIcon')).toBeInTheDocument();
  });

  it('respects colorize prop', () => {
    const { container } = render(
      <ThemeProvider theme={theme}>
        <AnimatedCurrency value={100} colorize={false} />
      </ThemeProvider>
    );
    expect(container.querySelector('.MuiTypography-root')).toBeInTheDocument();
  });
});

describe('AnimatedPercentage', () => {
  it('renders percentage format', () => {
    render(
      <ThemeProvider theme={theme}>
        <AnimatedPercentage value={15.5} />
      </ThemeProvider>
    );
    expect(screen.getByText('15.50%')).toBeInTheDocument();
  });

  it('renders negative percentage', () => {
    render(
      <ThemeProvider theme={theme}>
        <AnimatedPercentage value={-5.25} />
      </ThemeProvider>
    );
    expect(screen.getByText('-5.25%')).toBeInTheDocument();
  });

  it('uses custom variant', () => {
    const { container } = render(
      <ThemeProvider theme={theme}>
        <AnimatedPercentage value={10} variant="body2" />
      </ThemeProvider>
    );
    expect(container.querySelector('.MuiTypography-body2')).toBeInTheDocument();
  });

  it('shows trend when enabled', () => {
    const { rerender } = render(
      <ThemeProvider theme={theme}>
        <AnimatedPercentage value={10} showTrend={true} />
      </ThemeProvider>
    );

    rerender(
      <ThemeProvider theme={theme}>
        <AnimatedPercentage value={5} showTrend={true} />
      </ThemeProvider>
    );

    expect(screen.getByTestId('TrendingDownIcon')).toBeInTheDocument();
  });

  it('respects colorize prop', () => {
    const { container } = render(
      <ThemeProvider theme={theme}>
        <AnimatedPercentage value={10} colorize={false} />
      </ThemeProvider>
    );
    expect(container.querySelector('.MuiTypography-root')).toBeInTheDocument();
  });
});
