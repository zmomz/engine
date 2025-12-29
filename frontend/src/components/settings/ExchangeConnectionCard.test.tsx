import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { ThemeProvider } from '@mui/material/styles';
import { useForm, FormProvider } from 'react-hook-form';
import ExchangeConnectionCard from './ExchangeConnectionCard';
import { darkTheme } from '../../theme/theme';

// Wrapper component to provide form context
const FormWrapper: React.FC<{
  children: (control: any) => React.ReactNode;
  defaultValues?: Record<string, any>;
}> = ({ children, defaultValues = {} }) => {
  const methods = useForm({
    defaultValues: {
      exchangeSettings: {
        exchange: 'binance',
        ...defaultValues,
      },
    },
  });

  return (
    <FormProvider {...methods}>
      <form>{children(methods.control)}</form>
    </FormProvider>
  );
};

const renderWithProviders = (
  supportedExchanges = ['binance', 'bybit', 'kucoin'],
  configuredExchanges: string[] = ['binance'],
  activeExchange = 'binance',
  defaultValues?: Record<string, any>
) => {
  return render(
    <ThemeProvider theme={darkTheme}>
      <FormWrapper defaultValues={defaultValues}>
        {(control) => (
          <ExchangeConnectionCard
            control={control}
            supportedExchanges={supportedExchanges}
            configuredExchanges={configuredExchanges}
            activeExchange={activeExchange}
          />
        )}
      </FormWrapper>
    </ThemeProvider>
  );
};

describe('ExchangeConnectionCard', () => {
  describe('Rendering', () => {
    test('renders section title', () => {
      renderWithProviders();

      expect(screen.getByText('Exchange')).toBeInTheDocument();
    });

    test('renders section description', () => {
      renderWithProviders();

      expect(screen.getByText('Select your active trading exchange')).toBeInTheDocument();
    });
  });

  describe('Connection Status Chip', () => {
    test('shows Connected chip when exchange is configured', () => {
      renderWithProviders(['binance'], ['binance'], 'binance');

      expect(screen.getByText('Connected')).toBeInTheDocument();
    });

    test('shows Not Connected chip when exchange is not configured', () => {
      renderWithProviders(['binance', 'bybit'], [], 'binance');

      expect(screen.getByText('Not Connected')).toBeInTheDocument();
    });

    test('Connected chip has success color', () => {
      renderWithProviders(['binance'], ['binance'], 'binance');

      const chip = screen.getByText('Connected').closest('.MuiChip-root');
      expect(chip).toHaveClass('MuiChip-colorSuccess');
    });

    test('Not Connected chip has warning color', () => {
      renderWithProviders(['binance'], [], 'binance');

      const chip = screen.getByText('Not Connected').closest('.MuiChip-root');
      expect(chip).toHaveClass('MuiChip-colorWarning');
    });
  });

  describe('Exchange Selection', () => {
    test('renders Active Exchange select field', () => {
      renderWithProviders();

      expect(screen.getByLabelText(/active exchange/i)).toBeInTheDocument();
    });

    test('renders all supported exchanges as options', () => {
      renderWithProviders(['binance', 'bybit', 'kucoin']);

      const options = screen.getAllByRole('option');
      expect(options).toHaveLength(3);
    });

    test('shows checkmark for configured exchanges', () => {
      renderWithProviders(['binance', 'bybit', 'kucoin'], ['binance', 'kucoin']);

      // Binance and kucoin should have checkmark
      const binanceOption = screen.getByRole('option', { name: /binance/ });
      const kucoinOption = screen.getByRole('option', { name: /kucoin/ });
      const bybitOption = screen.getByRole('option', { name: /bybit/ });

      expect(binanceOption.textContent).toContain('✓');
      expect(kucoinOption.textContent).toContain('✓');
      expect(bybitOption.textContent).not.toContain('✓');
    });

    test('allows changing selected exchange', () => {
      renderWithProviders(['binance', 'bybit']);

      const select = screen.getByLabelText(/active exchange/i);
      fireEvent.change(select, { target: { value: 'bybit' } });

      expect(select).toHaveValue('bybit');
    });
  });

  describe('No API Keys Warning', () => {
    test('shows warning when active exchange has no API keys', () => {
      renderWithProviders(['binance', 'bybit'], [], 'binance');

      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText(/no api keys configured for this exchange/i)).toBeInTheDocument();
    });

    test('hides warning when active exchange has API keys', () => {
      renderWithProviders(['binance', 'bybit'], ['binance'], 'binance');

      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    });

    test('shows warning for unconfigured exchange even with others configured', () => {
      renderWithProviders(['binance', 'bybit'], ['bybit'], 'binance');

      expect(screen.getByText(/no api keys configured for this exchange/i)).toBeInTheDocument();
    });
  });

  describe('Default Values', () => {
    test('renders with default exchange value', () => {
      renderWithProviders(['binance', 'bybit'], ['binance'], 'binance', {
        exchange: 'binance',
      });

      expect(screen.getByLabelText(/active exchange/i)).toHaveValue('binance');
    });

    test('renders with different default exchange', () => {
      renderWithProviders(['binance', 'bybit'], ['bybit'], 'bybit', {
        exchange: 'bybit',
      });

      expect(screen.getByLabelText(/active exchange/i)).toHaveValue('bybit');
    });
  });

  describe('Single Exchange', () => {
    test('renders correctly with single supported exchange', () => {
      renderWithProviders(['binance'], ['binance'], 'binance');

      const options = screen.getAllByRole('option');
      expect(options).toHaveLength(1);
    });
  });

  describe('Multiple Exchanges', () => {
    test('renders all exchanges with correct configured status', () => {
      renderWithProviders(
        ['binance', 'bybit', 'kucoin', 'okx'],
        ['binance', 'okx'],
        'binance'
      );

      const options = screen.getAllByRole('option');
      expect(options).toHaveLength(4);

      // Check configured exchanges have checkmarks
      expect(options[0].textContent).toContain('binance');
      expect(options[0].textContent).toContain('✓');
      expect(options[3].textContent).toContain('okx');
      expect(options[3].textContent).toContain('✓');
    });
  });

  describe('Connection Status Changes', () => {
    test('connection status reflects activeExchange prop', () => {
      // Connected when activeExchange is in configuredExchanges
      const { rerender } = render(
        <ThemeProvider theme={darkTheme}>
          <FormWrapper>
            {(control) => (
              <ExchangeConnectionCard
                control={control}
                supportedExchanges={['binance', 'bybit']}
                configuredExchanges={['binance']}
                activeExchange="binance"
              />
            )}
          </FormWrapper>
        </ThemeProvider>
      );

      expect(screen.getByText('Connected')).toBeInTheDocument();

      // Re-render with activeExchange not in configuredExchanges
      rerender(
        <ThemeProvider theme={darkTheme}>
          <FormWrapper defaultValues={{ exchange: 'bybit' }}>
            {(control) => (
              <ExchangeConnectionCard
                control={control}
                supportedExchanges={['binance', 'bybit']}
                configuredExchanges={['binance']}
                activeExchange="bybit"
              />
            )}
          </FormWrapper>
        </ThemeProvider>
      );

      expect(screen.getByText('Not Connected')).toBeInTheDocument();
    });
  });
});
