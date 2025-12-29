import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { ThemeProvider } from '@mui/material/styles';
import { useForm, FormProvider } from 'react-hook-form';
import TimerConfigSection from './TimerConfigSection';
import { darkTheme } from '../../theme/theme';

// Wrapper component to provide form context
const FormWrapper: React.FC<{
  children: (control: any) => React.ReactNode;
  defaultValues?: Record<string, any>;
}> = ({ children, defaultValues = {} }) => {
  const methods = useForm({
    defaultValues: {
      riskEngineConfig: {
        loss_threshold_percent: -1.5,
        required_pyramids_for_timer: 3,
        post_pyramids_wait_minutes: 15,
        max_winners_to_combine: 2,
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
        {(control) => <TimerConfigSection control={control} errors={errors} />}
      </FormWrapper>
    </ThemeProvider>
  );
};

describe('TimerConfigSection', () => {
  describe('Rendering', () => {
    test('renders section title', () => {
      renderWithProviders();

      expect(screen.getByText('Timer Configuration')).toBeInTheDocument();
    });

    test('renders section description', () => {
      renderWithProviders();

      expect(screen.getByText('Offset execution timer settings')).toBeInTheDocument();
    });

    test('renders info alert', () => {
      renderWithProviders();

      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText(/timer starts when required pyramids filled/i)).toBeInTheDocument();
    });
  });

  describe('Form Fields', () => {
    test('renders loss threshold field', () => {
      renderWithProviders();

      expect(screen.getByLabelText(/loss threshold \(%\)/i)).toBeInTheDocument();
    });

    test('renders pyramids for timer field', () => {
      renderWithProviders();

      expect(screen.getByLabelText(/pyramids for timer/i)).toBeInTheDocument();
    });

    test('renders wait time field', () => {
      renderWithProviders();

      expect(screen.getByLabelText(/wait time \(min\)/i)).toBeInTheDocument();
    });

    test('renders max winners field', () => {
      renderWithProviders();

      expect(screen.getByLabelText(/max winners/i)).toBeInTheDocument();
    });

    test('displays default values', () => {
      renderWithProviders();

      expect(screen.getByDisplayValue('-1.5')).toBeInTheDocument();
      expect(screen.getByDisplayValue('3')).toBeInTheDocument();
      expect(screen.getByDisplayValue('15')).toBeInTheDocument();
      expect(screen.getByDisplayValue('2')).toBeInTheDocument();
    });
  });

  describe('Helper Text', () => {
    test('displays helper text for loss threshold', () => {
      renderWithProviders();

      expect(screen.getByText('e.g., -1.5%')).toBeInTheDocument();
    });

    test('displays helper text for pyramids required', () => {
      renderWithProviders();

      expect(screen.getByText('Required before timer starts')).toBeInTheDocument();
    });

    test('displays helper text for wait time', () => {
      renderWithProviders();

      expect(screen.getByText('Countdown before offset')).toBeInTheDocument();
    });

    test('displays helper text for max winners', () => {
      renderWithProviders();

      expect(screen.getByText('Winners for offset')).toBeInTheDocument();
    });
  });

  describe('Error States', () => {
    test('displays error for loss_threshold_percent', () => {
      const errors = {
        riskEngineConfig: {
          loss_threshold_percent: {
            message: 'Must be negative or zero',
          },
        },
      };

      renderWithProviders({}, errors);

      expect(screen.getByText('Must be negative or zero')).toBeInTheDocument();
    });

    test('displays error for required_pyramids_for_timer', () => {
      const errors = {
        riskEngineConfig: {
          required_pyramids_for_timer: {
            message: 'Must be between 1 and 10',
          },
        },
      };

      renderWithProviders({}, errors);

      expect(screen.getByText('Must be between 1 and 10')).toBeInTheDocument();
    });

    test('displays error for post_pyramids_wait_minutes', () => {
      const errors = {
        riskEngineConfig: {
          post_pyramids_wait_minutes: {
            message: 'Must be at least 0',
          },
        },
      };

      renderWithProviders({}, errors);

      expect(screen.getByText('Must be at least 0')).toBeInTheDocument();
    });

    test('displays error for max_winners_to_combine', () => {
      const errors = {
        riskEngineConfig: {
          max_winners_to_combine: {
            message: 'Invalid number',
          },
        },
      };

      renderWithProviders({}, errors);

      expect(screen.getByText('Invalid number')).toBeInTheDocument();
    });
  });

  describe('Input Interaction', () => {
    test('allows changing loss threshold', () => {
      renderWithProviders();

      const input = screen.getByLabelText(/loss threshold \(%\)/i);
      fireEvent.change(input, { target: { value: '-2.5' } });

      expect(input).toHaveValue(-2.5);
    });

    test('allows changing pyramids for timer', () => {
      renderWithProviders();

      const input = screen.getByLabelText(/pyramids for timer/i);
      fireEvent.change(input, { target: { value: '5' } });

      expect(input).toHaveValue(5);
    });

    test('allows changing wait time', () => {
      renderWithProviders();

      const input = screen.getByLabelText(/wait time \(min\)/i);
      fireEvent.change(input, { target: { value: '30' } });

      expect(input).toHaveValue(30);
    });

    test('allows changing max winners', () => {
      renderWithProviders();

      const input = screen.getByLabelText(/max winners/i);
      fireEvent.change(input, { target: { value: '5' } });

      expect(input).toHaveValue(5);
    });
  });

  describe('Custom Default Values', () => {
    test('renders with custom default values', () => {
      renderWithProviders({
        loss_threshold_percent: -3,
        required_pyramids_for_timer: 5,
        post_pyramids_wait_minutes: 30,
        max_winners_to_combine: 4,
      });

      expect(screen.getByDisplayValue('-3')).toBeInTheDocument();
      expect(screen.getByDisplayValue('5')).toBeInTheDocument();
      expect(screen.getByDisplayValue('30')).toBeInTheDocument();
      expect(screen.getByDisplayValue('4')).toBeInTheDocument();
    });
  });
});
