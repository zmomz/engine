import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { ThemeProvider, createTheme } from '@mui/material';
import { useForm, FormProvider } from 'react-hook-form';
import QueuePrioritySettings from './QueuePrioritySettings';

const theme = createTheme({
  palette: {
    mode: 'dark',
  },
});

// Wrapper component that provides form context
const TestWrapper: React.FC<{ defaultValues?: any; children?: React.ReactNode }> = ({
  defaultValues = {
    riskEngineConfig: {
      priority_rules: {
        priority_order: [
          'same_pair_timeframe',
          'deepest_loss_percent',
          'highest_replacement',
          'fifo_fallback',
        ],
        priority_rules_enabled: {
          same_pair_timeframe: true,
          deepest_loss_percent: true,
          highest_replacement: false,
          fifo_fallback: true,
        },
      },
    },
  },
}) => {
  const methods = useForm({ defaultValues });

  return (
    <ThemeProvider theme={theme}>
      <FormProvider {...methods}>
        <QueuePrioritySettings
          control={methods.control}
          setValue={methods.setValue}
          watch={methods.watch}
        />
      </FormProvider>
    </ThemeProvider>
  );
};

describe('QueuePrioritySettings', () => {
  describe('basic rendering', () => {
    it('renders title', () => {
      render(<TestWrapper />);
      expect(screen.getByText('Queue Priority Configuration')).toBeInTheDocument();
    });

    it('renders description', () => {
      render(<TestWrapper />);
      expect(screen.getByText('Configure priority rules and drag to reorder.')).toBeInTheDocument();
    });

    it('renders info box', () => {
      render(<TestWrapper />);
      expect(screen.getByText(/How it works/)).toBeInTheDocument();
    });
  });

  describe('priority rules', () => {
    it('renders all priority rules', () => {
      render(<TestWrapper />);

      expect(screen.getByText('Same Pair & Timeframe')).toBeInTheDocument();
      expect(screen.getByText('Deepest Current Loss')).toBeInTheDocument();
      expect(screen.getByText('Highest Replacement Count')).toBeInTheDocument();
      expect(screen.getByText('FIFO (First In First Out)')).toBeInTheDocument();
    });

    it('renders rule descriptions', () => {
      render(<TestWrapper />);

      expect(screen.getByText(/Pyramid continuation of an already active position/)).toBeInTheDocument();
      expect(screen.getByText(/Deeper loss means better discount zone/)).toBeInTheDocument();
      expect(screen.getByText(/Signal replaced multiple times/)).toBeInTheDocument();
      expect(screen.getByText(/Oldest queued signal/)).toBeInTheDocument();
    });

    it('renders priority order numbers', () => {
      render(<TestWrapper />);

      expect(screen.getByText('1')).toBeInTheDocument();
      expect(screen.getByText('2')).toBeInTheDocument();
      expect(screen.getByText('3')).toBeInTheDocument();
      expect(screen.getByText('4')).toBeInTheDocument();
    });
  });

  describe('rule toggles', () => {
    it('renders switches for each rule', () => {
      render(<TestWrapper />);

      // MUI Switch uses role="switch" instead of "checkbox"
      const switches = screen.getAllByRole('switch');
      expect(switches.length).toBe(4);
    });

    it('shows correct initial checked states', () => {
      render(<TestWrapper />);

      const switches = screen.getAllByRole('switch');
      // same_pair_timeframe = true
      expect(switches[0]).toBeChecked();
      // deepest_loss_percent = true
      expect(switches[1]).toBeChecked();
      // highest_replacement = false
      expect(switches[2]).not.toBeChecked();
      // fifo_fallback = true
      expect(switches[3]).toBeChecked();
    });

    it('toggles rule when switch clicked', () => {
      render(<TestWrapper />);

      const switches = screen.getAllByRole('switch');
      // Toggle highest_replacement on
      fireEvent.click(switches[2]);
      expect(switches[2]).toBeChecked();
    });
  });

  describe('warning states', () => {
    it('shows warning when no rules enabled', () => {
      render(
        <TestWrapper
          defaultValues={{
            riskEngineConfig: {
              priority_rules: {
                priority_order: ['same_pair_timeframe', 'deepest_loss_percent', 'highest_replacement', 'fifo_fallback'],
                priority_rules_enabled: {
                  same_pair_timeframe: false,
                  deepest_loss_percent: false,
                  highest_replacement: false,
                  fifo_fallback: false,
                },
              },
            },
          }}
        />
      );

      expect(screen.getByText('At least one priority rule must be enabled')).toBeInTheDocument();
    });

    it('does not show warning when at least one rule enabled', () => {
      render(<TestWrapper />);

      expect(screen.queryByText('At least one priority rule must be enabled')).not.toBeInTheDocument();
    });
  });

  describe('drag indicators', () => {
    it('renders drag indicators for each rule', () => {
      render(<TestWrapper />);

      const dragIcons = screen.getAllByTestId('DragIndicatorIcon');
      expect(dragIcons.length).toBe(4);
    });
  });

  describe('missing rule handling', () => {
    it('handles unknown rule names gracefully', () => {
      render(
        <TestWrapper
          defaultValues={{
            riskEngineConfig: {
              priority_rules: {
                priority_order: ['unknown_rule', 'same_pair_timeframe'],
                priority_rules_enabled: {
                  unknown_rule: true,
                  same_pair_timeframe: true,
                },
              },
            },
          }}
        />
      );

      // Should still render known rules
      expect(screen.getByText('Same Pair & Timeframe')).toBeInTheDocument();
    });
  });

  describe('default values', () => {
    it('uses default priority order when not provided', () => {
      render(
        <TestWrapper
          defaultValues={{
            riskEngineConfig: {
              priority_rules: {
                priority_order: null,
                priority_rules_enabled: {},
              },
            },
          }}
        />
      );

      // Should use default order
      expect(screen.getByText('Same Pair & Timeframe')).toBeInTheDocument();
    });
  });
});
