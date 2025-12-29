import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { ThemeProvider } from '@mui/material/styles';
import { useForm, FormProvider } from 'react-hook-form';
import RiskLimitsSection from './RiskLimitsSection';
import { darkTheme } from '../../theme/theme';

// Wrapper component to provide form context
const FormWrapper: React.FC<{
  children: (control: any) => React.ReactNode;
  defaultValues?: Record<string, any>;
}> = ({ children, defaultValues = {} }) => {
  const methods = useForm({
    defaultValues: {
      riskEngineConfig: {
        max_open_positions_global: 10,
        max_open_positions_per_symbol: 2,
        max_total_exposure_usd: 5000,
        max_realized_loss_usd: 500,
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
  defaultValues?: Record<string, any>,
  errors?: Record<string, any>
) => {
  return render(
    <ThemeProvider theme={darkTheme}>
      <FormWrapper defaultValues={defaultValues}>
        {(control) => <RiskLimitsSection control={control} errors={errors} />}
      </FormWrapper>
    </ThemeProvider>
  );
};

describe('RiskLimitsSection', () => {
  describe('Rendering', () => {
    test('renders section title', () => {
      renderWithProviders();

      expect(screen.getByText('Pre-Trade Risk Limits')).toBeInTheDocument();
    });

    test('renders section description', () => {
      renderWithProviders();

      expect(screen.getByText('Configure position and exposure limits')).toBeInTheDocument();
    });

    test('renders info alert', () => {
      renderWithProviders();

      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText(/limits checked before opening positions/i)).toBeInTheDocument();
    });
  });

  describe('Form Fields', () => {
    test('renders max positions global field', () => {
      renderWithProviders();

      expect(screen.getByLabelText(/max positions \(global\)/i)).toBeInTheDocument();
    });

    test('renders max per symbol field', () => {
      renderWithProviders();

      expect(screen.getByLabelText(/max per symbol/i)).toBeInTheDocument();
    });

    test('renders max exposure USD field', () => {
      renderWithProviders();

      expect(screen.getByLabelText(/max exposure \(usd\)/i)).toBeInTheDocument();
    });

    test('renders loss limit USD field', () => {
      renderWithProviders();

      expect(screen.getByLabelText(/loss limit \(usd\)/i)).toBeInTheDocument();
    });

    test('displays default values', () => {
      renderWithProviders();

      expect(screen.getByDisplayValue('10')).toBeInTheDocument();
      expect(screen.getByDisplayValue('2')).toBeInTheDocument();
      expect(screen.getByDisplayValue('5000')).toBeInTheDocument();
      expect(screen.getByDisplayValue('500')).toBeInTheDocument();
    });
  });

  describe('Helper Text', () => {
    test('displays helper text for max positions', () => {
      renderWithProviders();

      expect(screen.getByText('Max total positions')).toBeInTheDocument();
    });

    test('displays helper text for max per pair', () => {
      renderWithProviders();

      expect(screen.getByText('Max per pair')).toBeInTheDocument();
    });

    test('displays helper text for max capital deployed', () => {
      renderWithProviders();

      expect(screen.getByText('Max capital deployed')).toBeInTheDocument();
    });

    test('displays helper text for circuit breaker', () => {
      renderWithProviders();

      expect(screen.getByText('Circuit breaker')).toBeInTheDocument();
    });
  });

  describe('Error States', () => {
    test('displays error for max_open_positions_global', () => {
      const errors = {
        riskEngineConfig: {
          max_open_positions_global: {
            message: 'Must be at least 0',
          },
        },
      };

      renderWithProviders({}, errors);

      expect(screen.getByText('Must be at least 0')).toBeInTheDocument();
    });

    test('displays error for max_open_positions_per_symbol', () => {
      const errors = {
        riskEngineConfig: {
          max_open_positions_per_symbol: {
            message: 'Invalid value',
          },
        },
      };

      renderWithProviders({}, errors);

      expect(screen.getByText('Invalid value')).toBeInTheDocument();
    });

    test('displays error for max_total_exposure_usd', () => {
      const errors = {
        riskEngineConfig: {
          max_total_exposure_usd: {
            message: 'Required field',
          },
        },
      };

      renderWithProviders({}, errors);

      expect(screen.getByText('Required field')).toBeInTheDocument();
    });

    test('displays error for max_realized_loss_usd', () => {
      const errors = {
        riskEngineConfig: {
          max_realized_loss_usd: {
            message: 'Must be positive',
          },
        },
      };

      renderWithProviders({}, errors);

      expect(screen.getByText('Must be positive')).toBeInTheDocument();
    });
  });

  describe('Input Interaction', () => {
    test('allows changing max positions global', () => {
      renderWithProviders();

      const input = screen.getByLabelText(/max positions \(global\)/i);
      fireEvent.change(input, { target: { value: '20' } });

      expect(input).toHaveValue(20);
    });

    test('allows changing max per symbol', () => {
      renderWithProviders();

      const input = screen.getByLabelText(/max per symbol/i);
      fireEvent.change(input, { target: { value: '5' } });

      expect(input).toHaveValue(5);
    });

    test('allows changing max exposure', () => {
      renderWithProviders();

      const input = screen.getByLabelText(/max exposure \(usd\)/i);
      fireEvent.change(input, { target: { value: '10000' } });

      expect(input).toHaveValue(10000);
    });

    test('allows changing loss limit', () => {
      renderWithProviders();

      const input = screen.getByLabelText(/loss limit \(usd\)/i);
      fireEvent.change(input, { target: { value: '1000' } });

      expect(input).toHaveValue(1000);
    });
  });

  describe('Custom Default Values', () => {
    test('renders with custom default values', () => {
      renderWithProviders({
        max_open_positions_global: 25,
        max_open_positions_per_symbol: 3,
        max_total_exposure_usd: 15000,
        max_realized_loss_usd: 1500,
      });

      expect(screen.getByDisplayValue('25')).toBeInTheDocument();
      expect(screen.getByDisplayValue('3')).toBeInTheDocument();
      expect(screen.getByDisplayValue('15000')).toBeInTheDocument();
      expect(screen.getByDisplayValue('1500')).toBeInTheDocument();
    });
  });
});
