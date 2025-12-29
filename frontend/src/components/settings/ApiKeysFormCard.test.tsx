import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { ThemeProvider } from '@mui/material/styles';
import { useForm, FormProvider } from 'react-hook-form';
import ApiKeysFormCard from './ApiKeysFormCard';
import { darkTheme } from '../../theme/theme';

// Wrapper component to provide form context
const FormWrapper: React.FC<{
  children: (props: { control: any; watch: any }) => React.ReactNode;
  defaultValues?: Record<string, any>;
}> = ({ children, defaultValues = {} }) => {
  const methods = useForm({
    defaultValues: {
      exchangeSettings: {
        key_target_exchange: 'binance',
        account_type: 'UNIFIED',
        api_key: '',
        secret_key: '',
        testnet: false,
        ...defaultValues,
      },
    },
  });

  return (
    <FormProvider {...methods}>
      <form>{children({ control: methods.control, watch: methods.watch })}</form>
    </FormProvider>
  );
};

const renderWithProviders = (
  supportedExchanges = ['binance', 'bybit', 'kucoin'],
  configuredExchanges: string[] = [],
  defaultValues?: Record<string, any>,
  errors?: Record<string, any>
) => {
  const mockOnSaveKeys = jest.fn();

  const { container } = render(
    <ThemeProvider theme={darkTheme}>
      <FormWrapper defaultValues={defaultValues}>
        {({ control, watch }) => (
          <ApiKeysFormCard
            control={control}
            watch={watch}
            supportedExchanges={supportedExchanges}
            configuredExchanges={configuredExchanges}
            onSaveKeys={mockOnSaveKeys}
            errors={errors}
          />
        )}
      </FormWrapper>
    </ThemeProvider>
  );

  return { mockOnSaveKeys, container };
};

describe('ApiKeysFormCard', () => {
  describe('Rendering', () => {
    test('renders section title', () => {
      renderWithProviders();

      expect(screen.getByText('Add API Keys')).toBeInTheDocument();
    });

    test('renders section description', () => {
      renderWithProviders();

      expect(screen.getByText('Configure API credentials for an exchange')).toBeInTheDocument();
    });
  });

  describe('Form Fields', () => {
    test('renders exchange select field', () => {
      renderWithProviders();

      expect(screen.getByLabelText(/exchange/i)).toBeInTheDocument();
    });

    test('renders account type field', () => {
      renderWithProviders();

      expect(screen.getByLabelText(/account type/i)).toBeInTheDocument();
    });

    test('renders API key field', () => {
      renderWithProviders();

      expect(screen.getByLabelText(/api key/i)).toBeInTheDocument();
    });

    test('renders secret key field', () => {
      renderWithProviders();

      expect(screen.getByLabelText(/secret key/i)).toBeInTheDocument();
    });

    test('renders testnet checkbox', () => {
      renderWithProviders();

      expect(screen.getByLabelText(/testnet/i)).toBeInTheDocument();
    });

    test('renders save button', () => {
      renderWithProviders();

      expect(screen.getByRole('button', { name: /save/i })).toBeInTheDocument();
    });
  });

  describe('Exchange Selection', () => {
    test('renders all supported exchanges as options', () => {
      renderWithProviders(['binance', 'bybit', 'kucoin']);

      const select = screen.getByLabelText(/exchange/i);
      expect(select).toBeInTheDocument();

      // Check options exist
      const options = screen.getAllByRole('option');
      expect(options).toHaveLength(3);
    });

    test('allows changing selected exchange', () => {
      renderWithProviders(['binance', 'bybit']);

      const select = screen.getByLabelText(/exchange/i);
      fireEvent.change(select, { target: { value: 'bybit' } });

      expect(select).toHaveValue('bybit');
    });
  });

  describe('Not Configured Warning', () => {
    test('shows warning when selected exchange is not configured', () => {
      renderWithProviders(['binance', 'bybit'], []);

      // Default is binance, which is not in configuredExchanges
      expect(screen.getByText(/no keys found for binance/i)).toBeInTheDocument();
    });

    test('hides warning when selected exchange is already configured', () => {
      renderWithProviders(['binance', 'bybit'], ['binance']);

      expect(screen.queryByText(/no keys found for/i)).not.toBeInTheDocument();
    });
  });

  describe('Input Interaction', () => {
    test('allows entering API key', () => {
      renderWithProviders();

      const input = screen.getByLabelText(/api key/i);
      fireEvent.change(input, { target: { value: 'my-api-key-123' } });

      expect(input).toHaveValue('my-api-key-123');
    });

    test('allows entering secret key', () => {
      renderWithProviders();

      const input = screen.getByLabelText(/secret key/i);
      fireEvent.change(input, { target: { value: 'my-secret-key-456' } });

      expect(input).toHaveValue('my-secret-key-456');
    });

    test('allows entering account type', () => {
      renderWithProviders();

      const input = screen.getByLabelText(/account type/i);
      fireEvent.change(input, { target: { value: 'SPOT' } });

      expect(input).toHaveValue('SPOT');
    });

    test('allows toggling testnet checkbox', () => {
      renderWithProviders();

      const checkbox = screen.getByLabelText(/testnet/i);
      expect(checkbox).not.toBeChecked();

      fireEvent.click(checkbox);
      expect(checkbox).toBeChecked();

      fireEvent.click(checkbox);
      expect(checkbox).not.toBeChecked();
    });
  });

  describe('Save Button', () => {
    test('calls onSaveKeys when save button is clicked', () => {
      const { mockOnSaveKeys } = renderWithProviders();

      const saveButton = screen.getByRole('button', { name: /save/i });
      fireEvent.click(saveButton);

      expect(mockOnSaveKeys).toHaveBeenCalled();
    });
  });

  describe('Error States', () => {
    test('displays error for exchange selection', () => {
      const errors = {
        exchangeSettings: {
          key_target_exchange: {
            message: 'Exchange is required',
          },
        },
      };

      renderWithProviders(['binance'], [], undefined, errors);

      const select = screen.getByLabelText(/exchange/i);
      // MUI shows error state on the input
      expect(select.closest('.MuiFormControl-root')).toBeInTheDocument();
    });

    test('displays error for API key', () => {
      const errors = {
        exchangeSettings: {
          api_key: {
            message: 'API key is required',
          },
        },
      };

      renderWithProviders(['binance'], [], undefined, errors);

      const input = screen.getByLabelText(/api key/i);
      expect(input.closest('.MuiFormControl-root')).toBeInTheDocument();
    });

    test('displays error for secret key', () => {
      const errors = {
        exchangeSettings: {
          secret_key: {
            message: 'Secret key is required',
          },
        },
      };

      renderWithProviders(['binance'], [], undefined, errors);

      const input = screen.getByLabelText(/secret key/i);
      expect(input.closest('.MuiFormControl-root')).toBeInTheDocument();
    });
  });

  describe('Default Values', () => {
    test('renders with custom default values', () => {
      renderWithProviders(['binance', 'bybit'], ['bybit'], {
        key_target_exchange: 'bybit',
        account_type: 'FUTURES',
        api_key: 'existing-key',
        secret_key: 'existing-secret',
        testnet: true,
      });

      expect(screen.getByLabelText(/exchange/i)).toHaveValue('bybit');
      expect(screen.getByLabelText(/account type/i)).toHaveValue('FUTURES');
      expect(screen.getByLabelText(/api key/i)).toHaveValue('existing-key');
      expect(screen.getByLabelText(/secret key/i)).toHaveValue('existing-secret');
      expect(screen.getByLabelText(/testnet/i)).toBeChecked();
    });

    test('secret key field is password type', () => {
      renderWithProviders();

      const input = screen.getByLabelText(/secret key/i);
      expect(input).toHaveAttribute('type', 'password');
    });
  });

  describe('Single Exchange', () => {
    test('renders correctly with single supported exchange', () => {
      renderWithProviders(['binance'], []);

      const options = screen.getAllByRole('option');
      expect(options).toHaveLength(1);
    });
  });

  describe('Account Type Placeholder', () => {
    test('shows placeholder for account type', () => {
      renderWithProviders();

      const input = screen.getByLabelText(/account type/i);
      expect(input).toHaveAttribute('placeholder', 'UNIFIED');
    });
  });
});
