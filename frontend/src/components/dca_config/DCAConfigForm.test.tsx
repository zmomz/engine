import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ThemeProvider } from '@mui/material/styles';
import DCAConfigForm from './DCAConfigForm';
import { darkTheme } from '../../theme/theme';
import { DCAConfiguration } from '../../api/dcaConfig';

// Mock useMediaQuery
jest.mock('@mui/material', () => {
  const actual = jest.requireActual('@mui/material');
  return {
    ...actual,
    useMediaQuery: jest.fn().mockReturnValue(false),
  };
});

const renderWithTheme = (component: React.ReactElement) => {
  return render(
    <ThemeProvider theme={darkTheme}>{component}</ThemeProvider>
  );
};

const mockInitialData: DCAConfiguration = {
  id: 'config-123',
  user_id: 'user-123',
  pair: 'BTC/USDT',
  timeframe: 60,
  exchange: 'binance',
  entry_order_type: 'limit',
  dca_levels: [
    { gap_percent: 0, weight_percent: 50, tp_percent: 2 },
    { gap_percent: 1, weight_percent: 50, tp_percent: 3 },
  ],
  tp_mode: 'per_leg',
  tp_settings: {},
  max_pyramids: 5,
  use_custom_capital: false,
  custom_capital_usd: 200,
};

describe('DCAConfigForm', () => {
  const mockOnClose = jest.fn();
  const mockOnSubmit = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    mockOnSubmit.mockResolvedValue(undefined);
  });

  describe('Dialog Rendering', () => {
    test('renders dialog when open', () => {
      renderWithTheme(
        <DCAConfigForm
          open={true}
          onClose={mockOnClose}
          onSubmit={mockOnSubmit}
        />
      );

      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    test('does not render dialog when closed', () => {
      renderWithTheme(
        <DCAConfigForm
          open={false}
          onClose={mockOnClose}
          onSubmit={mockOnSubmit}
        />
      );

      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    test('shows Create title when not editing', () => {
      renderWithTheme(
        <DCAConfigForm
          open={true}
          onClose={mockOnClose}
          onSubmit={mockOnSubmit}
          isEdit={false}
        />
      );

      expect(screen.getByText('Create DCA Configuration')).toBeInTheDocument();
    });

    test('shows Edit title when editing', () => {
      renderWithTheme(
        <DCAConfigForm
          open={true}
          onClose={mockOnClose}
          onSubmit={mockOnSubmit}
          initialData={mockInitialData}
          isEdit={true}
        />
      );

      expect(screen.getByText('Edit DCA Configuration')).toBeInTheDocument();
    });
  });

  describe('Form Fields', () => {
    test('renders all basic fields', () => {
      renderWithTheme(
        <DCAConfigForm
          open={true}
          onClose={mockOnClose}
          onSubmit={mockOnSubmit}
        />
      );

      expect(screen.getByLabelText(/pair/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/tf \(min\)/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/exchange/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/entry type/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/max pyramids/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/tp mode/i)).toBeInTheDocument();
    });

    test('populates fields with initial data', () => {
      renderWithTheme(
        <DCAConfigForm
          open={true}
          onClose={mockOnClose}
          onSubmit={mockOnSubmit}
          initialData={mockInitialData}
          isEdit={true}
        />
      );

      expect(screen.getByDisplayValue('BTC/USDT')).toBeInTheDocument();
      expect(screen.getByDisplayValue('60')).toBeInTheDocument();
      expect(screen.getByDisplayValue('binance')).toBeInTheDocument();
      expect(screen.getByDisplayValue('5')).toBeInTheDocument();
    });

    test('disables pair, timeframe, and exchange when editing', () => {
      renderWithTheme(
        <DCAConfigForm
          open={true}
          onClose={mockOnClose}
          onSubmit={mockOnSubmit}
          initialData={mockInitialData}
          isEdit={true}
        />
      );

      expect(screen.getByLabelText(/pair/i)).toBeDisabled();
      expect(screen.getByLabelText(/tf \(min\)/i)).toBeDisabled();
      expect(screen.getByLabelText(/exchange/i)).toBeDisabled();
    });
  });

  describe('TP Mode Settings', () => {
    test('shows aggregate TP field when aggregate mode selected', async () => {
      renderWithTheme(
        <DCAConfigForm
          open={true}
          onClose={mockOnClose}
          onSubmit={mockOnSubmit}
          initialData={{
            ...mockInitialData,
            tp_mode: 'aggregate',
            tp_settings: { tp_aggregate_percent: 2.5 },
          }}
          isEdit={true}
        />
      );

      expect(screen.getByLabelText(/agg tp %/i)).toBeInTheDocument();
    });

    test('shows aggregate TP field when hybrid mode selected', async () => {
      renderWithTheme(
        <DCAConfigForm
          open={true}
          onClose={mockOnClose}
          onSubmit={mockOnSubmit}
          initialData={{
            ...mockInitialData,
            tp_mode: 'hybrid',
          }}
          isEdit={true}
        />
      );

      expect(screen.getByLabelText(/agg tp %/i)).toBeInTheDocument();
    });

    test('shows aggregate TP field when pyramid_aggregate mode selected', async () => {
      renderWithTheme(
        <DCAConfigForm
          open={true}
          onClose={mockOnClose}
          onSubmit={mockOnSubmit}
          initialData={{
            ...mockInitialData,
            tp_mode: 'pyramid_aggregate',
          }}
          isEdit={true}
        />
      );

      expect(screen.getByLabelText(/agg tp %/i)).toBeInTheDocument();
    });

    test('hides aggregate TP field when per_leg mode selected', async () => {
      renderWithTheme(
        <DCAConfigForm
          open={true}
          onClose={mockOnClose}
          onSubmit={mockOnSubmit}
          initialData={{
            ...mockInitialData,
            tp_mode: 'per_leg',
          }}
          isEdit={true}
        />
      );

      expect(screen.queryByLabelText(/agg tp %/i)).not.toBeInTheDocument();
    });
  });

  describe('Capital Override Settings', () => {
    test('shows capital override switch', () => {
      renderWithTheme(
        <DCAConfigForm
          open={true}
          onClose={mockOnClose}
          onSubmit={mockOnSubmit}
        />
      );

      expect(screen.getByText(/override webhook position size/i)).toBeInTheDocument();
    });

    test('shows default capital field when custom capital enabled', async () => {
      renderWithTheme(
        <DCAConfigForm
          open={true}
          onClose={mockOnClose}
          onSubmit={mockOnSubmit}
          initialData={{
            ...mockInitialData,
            use_custom_capital: true,
            custom_capital_usd: 500,
          }}
          isEdit={true}
        />
      );

      expect(screen.getByLabelText(/default capital/i)).toBeInTheDocument();
    });

    test('hides capital field when custom capital disabled', () => {
      renderWithTheme(
        <DCAConfigForm
          open={true}
          onClose={mockOnClose}
          onSubmit={mockOnSubmit}
          initialData={{
            ...mockInitialData,
            use_custom_capital: false,
          }}
          isEdit={true}
        />
      );

      expect(screen.queryByLabelText(/default capital/i)).not.toBeInTheDocument();
    });
  });

  describe('DCA Levels Tabs', () => {
    test('shows Default tab', () => {
      renderWithTheme(
        <DCAConfigForm
          open={true}
          onClose={mockOnClose}
          onSubmit={mockOnSubmit}
        />
      );

      expect(screen.getByRole('tab', { name: /default/i })).toBeInTheDocument();
    });

    test('shows pyramid tabs based on max_pyramids', () => {
      renderWithTheme(
        <DCAConfigForm
          open={true}
          onClose={mockOnClose}
          onSubmit={mockOnSubmit}
          initialData={{
            ...mockInitialData,
            max_pyramids: 3,
          }}
          isEdit={true}
        />
      );

      expect(screen.getByRole('tab', { name: /p1/i })).toBeInTheDocument();
      expect(screen.getByRole('tab', { name: /p2/i })).toBeInTheDocument();
      expect(screen.getByRole('tab', { name: /p3/i })).toBeInTheDocument();
    });

    test('switches to pyramid tab when clicked', async () => {
      renderWithTheme(
        <DCAConfigForm
          open={true}
          onClose={mockOnClose}
          onSubmit={mockOnSubmit}
          initialData={{
            ...mockInitialData,
            max_pyramids: 3,
          }}
          isEdit={true}
        />
      );

      const p1Tab = screen.getByRole('tab', { name: /p1/i });
      fireEvent.click(p1Tab);

      await waitFor(() => {
        expect(screen.getByText(/pyramid 1 config/i)).toBeInTheDocument();
      });
    });
  });

  describe('DCA Levels Editor', () => {
    test('shows Add Level button', () => {
      renderWithTheme(
        <DCAConfigForm
          open={true}
          onClose={mockOnClose}
          onSubmit={mockOnSubmit}
        />
      );

      expect(screen.getByRole('button', { name: /add level/i })).toBeInTheDocument();
    });

    test('shows existing DCA levels', () => {
      renderWithTheme(
        <DCAConfigForm
          open={true}
          onClose={mockOnClose}
          onSubmit={mockOnSubmit}
          initialData={mockInitialData}
          isEdit={true}
        />
      );

      // Should show level indices
      expect(screen.getByText('#0')).toBeInTheDocument();
      expect(screen.getByText('#1')).toBeInTheDocument();
    });

    test('adds new level when Add Level clicked', async () => {
      renderWithTheme(
        <DCAConfigForm
          open={true}
          onClose={mockOnClose}
          onSubmit={mockOnSubmit}
        />
      );

      const addButton = screen.getByRole('button', { name: /add level/i });
      fireEvent.click(addButton);

      await waitFor(() => {
        expect(screen.getByText('#0')).toBeInTheDocument();
      });
    });
  });

  describe('Form Actions', () => {
    test('calls onClose when Cancel clicked', () => {
      renderWithTheme(
        <DCAConfigForm
          open={true}
          onClose={mockOnClose}
          onSubmit={mockOnSubmit}
        />
      );

      fireEvent.click(screen.getByRole('button', { name: /cancel/i }));

      expect(mockOnClose).toHaveBeenCalled();
    });

    test('has Save button', () => {
      renderWithTheme(
        <DCAConfigForm
          open={true}
          onClose={mockOnClose}
          onSubmit={mockOnSubmit}
        />
      );

      expect(screen.getByRole('button', { name: /save/i })).toBeInTheDocument();
    });
  });

  describe('Form Reset', () => {
    test('resets form when dialog opens with new data', async () => {
      const { rerender } = renderWithTheme(
        <DCAConfigForm
          open={false}
          onClose={mockOnClose}
          onSubmit={mockOnSubmit}
        />
      );

      rerender(
        <ThemeProvider theme={darkTheme}>
          <DCAConfigForm
            open={true}
            onClose={mockOnClose}
            onSubmit={mockOnSubmit}
            initialData={mockInitialData}
            isEdit={true}
          />
        </ThemeProvider>
      );

      await waitFor(() => {
        expect(screen.getByDisplayValue('BTC/USDT')).toBeInTheDocument();
      });
    });

    test('resets to defaults when creating new config', async () => {
      const { rerender } = renderWithTheme(
        <DCAConfigForm
          open={false}
          onClose={mockOnClose}
          onSubmit={mockOnSubmit}
        />
      );

      rerender(
        <ThemeProvider theme={darkTheme}>
          <DCAConfigForm
            open={true}
            onClose={mockOnClose}
            onSubmit={mockOnSubmit}
            isEdit={false}
          />
        </ThemeProvider>
      );

      await waitFor(() => {
        expect(screen.getByDisplayValue('60')).toBeInTheDocument(); // Default timeframe
        expect(screen.getByDisplayValue('binance')).toBeInTheDocument(); // Default exchange
      });
    });
  });

  describe('Info Alerts', () => {
    test('shows info alert on Default tab', () => {
      renderWithTheme(
        <DCAConfigForm
          open={true}
          onClose={mockOnClose}
          onSubmit={mockOnSubmit}
        />
      );

      expect(screen.getByText(/default levels for initial position/i)).toBeInTheDocument();
    });

    test('shows info alert on pyramid tab', async () => {
      renderWithTheme(
        <DCAConfigForm
          open={true}
          onClose={mockOnClose}
          onSubmit={mockOnSubmit}
          initialData={{
            ...mockInitialData,
            max_pyramids: 2,
          }}
          isEdit={true}
        />
      );

      const p1Tab = screen.getByRole('tab', { name: /p1/i });
      fireEvent.click(p1Tab);

      await waitFor(() => {
        expect(screen.getByText(/pyramid 1 config/i)).toBeInTheDocument();
      });
    });
  });

  describe('Pyramid Override Checkbox', () => {
    test('shows enable checkbox on pyramid tab', async () => {
      renderWithTheme(
        <DCAConfigForm
          open={true}
          onClose={mockOnClose}
          onSubmit={mockOnSubmit}
          initialData={{
            ...mockInitialData,
            max_pyramids: 2,
          }}
          isEdit={true}
        />
      );

      const p1Tab = screen.getByRole('tab', { name: /p1/i });
      fireEvent.click(p1Tab);

      await waitFor(() => {
        expect(screen.getByText(/enable p1 dca levels/i)).toBeInTheDocument();
      });
    });
  });

  describe('Take Profit Section', () => {
    test('displays Take Profit section header', () => {
      renderWithTheme(
        <DCAConfigForm
          open={true}
          onClose={mockOnClose}
          onSubmit={mockOnSubmit}
        />
      );

      expect(screen.getByText('Take Profit')).toBeInTheDocument();
    });
  });

  describe('Capital Size Section', () => {
    test('displays Capital Size section header', () => {
      renderWithTheme(
        <DCAConfigForm
          open={true}
          onClose={mockOnClose}
          onSubmit={mockOnSubmit}
        />
      );

      expect(screen.getByText('Capital Size')).toBeInTheDocument();
    });

    test('shows webhook message when custom capital disabled', () => {
      renderWithTheme(
        <DCAConfigForm
          open={true}
          onClose={mockOnClose}
          onSubmit={mockOnSubmit}
        />
      );

      expect(screen.getByText(/using position size from tradingview webhook signal/i)).toBeInTheDocument();
    });
  });

  describe('DCA Levels Section', () => {
    test('displays DCA Levels section header', () => {
      renderWithTheme(
        <DCAConfigForm
          open={true}
          onClose={mockOnClose}
          onSubmit={mockOnSubmit}
        />
      );

      expect(screen.getByText('DCA Levels')).toBeInTheDocument();
    });
  });

  describe('Form Submission', () => {
    test('calls onSubmit with form data when Save clicked', async () => {
      const mockData: DCAConfiguration = {
        id: 'test-123',
        user_id: 'user-123',
        pair: 'ETH/USDT',
        timeframe: 15,
        exchange: 'binance',
        entry_order_type: 'limit',
        dca_levels: [
          { gap_percent: 0, weight_percent: 100, tp_percent: 2 },
        ],
        tp_mode: 'per_leg',
        tp_settings: {},
        max_pyramids: 3,
        use_custom_capital: false,
        custom_capital_usd: 200,
      };

      renderWithTheme(
        <DCAConfigForm
          open={true}
          onClose={mockOnClose}
          onSubmit={mockOnSubmit}
          initialData={mockData}
          isEdit={true}
        />
      );

      const saveButton = screen.getByRole('button', { name: /save/i });
      fireEvent.click(saveButton);

      await waitFor(() => {
        expect(mockOnSubmit).toHaveBeenCalled();
      });
    });
  });

  describe('Pyramid Tab Interactions', () => {
    test('can enable pyramid-specific levels', async () => {
      renderWithTheme(
        <DCAConfigForm
          open={true}
          onClose={mockOnClose}
          onSubmit={mockOnSubmit}
          initialData={{
            ...mockInitialData,
            max_pyramids: 2,
          }}
          isEdit={true}
        />
      );

      // Switch to P1 tab
      const p1Tab = screen.getByRole('tab', { name: /p1/i });
      fireEvent.click(p1Tab);

      await waitFor(() => {
        // Should show enable checkbox
        expect(screen.getByText(/enable p1 dca levels/i)).toBeInTheDocument();
      });
    });

    test('shows P2 tab for max_pyramids >= 2', () => {
      renderWithTheme(
        <DCAConfigForm
          open={true}
          onClose={mockOnClose}
          onSubmit={mockOnSubmit}
          initialData={{
            ...mockInitialData,
            max_pyramids: 2,
          }}
          isEdit={true}
        />
      );

      expect(screen.getByRole('tab', { name: /p2/i })).toBeInTheDocument();
    });
  });

  describe('DCA Level Removal', () => {
    test('shows delete button for each level', () => {
      renderWithTheme(
        <DCAConfigForm
          open={true}
          onClose={mockOnClose}
          onSubmit={mockOnSubmit}
          initialData={mockInitialData}
          isEdit={true}
        />
      );

      const deleteButtons = screen.getAllByTestId('DeleteIcon');
      expect(deleteButtons.length).toBe(2); // Two levels in mockInitialData
    });
  });

  describe('TP Mode interactions', () => {
    test('shows aggregate TP field in aggregate mode', () => {
      renderWithTheme(
        <DCAConfigForm
          open={true}
          onClose={mockOnClose}
          onSubmit={mockOnSubmit}
          initialData={{
            ...mockInitialData,
            tp_mode: 'aggregate',
            tp_settings: { tp_aggregate_percent: 2.5 },
          }}
          isEdit={true}
        />
      );

      // Should show the Agg TP % field
      expect(screen.getByLabelText(/agg tp %/i)).toBeInTheDocument();
    });

    test('per_leg mode does not show aggregate TP field', () => {
      renderWithTheme(
        <DCAConfigForm
          open={true}
          onClose={mockOnClose}
          onSubmit={mockOnSubmit}
          initialData={{
            ...mockInitialData,
            tp_mode: 'per_leg',
          }}
          isEdit={true}
        />
      );

      // Should not show the Agg TP % field
      expect(screen.queryByLabelText(/agg tp %/i)).not.toBeInTheDocument();
    });
  });

  describe('Entry Order Type', () => {
    test('can select market entry type', () => {
      renderWithTheme(
        <DCAConfigForm
          open={true}
          onClose={mockOnClose}
          onSubmit={mockOnSubmit}
          initialData={{
            ...mockInitialData,
            entry_order_type: 'market',
          }}
          isEdit={true}
        />
      );

      expect(screen.getByDisplayValue('market')).toBeInTheDocument();
    });
  });

  describe('Custom Capital Toggle', () => {
    test('shows using webhook message when custom capital is off', () => {
      renderWithTheme(
        <DCAConfigForm
          open={true}
          onClose={mockOnClose}
          onSubmit={mockOnSubmit}
          initialData={{
            ...mockInitialData,
            use_custom_capital: false,
          }}
          isEdit={true}
        />
      );

      expect(screen.getByText(/using position size from tradingview webhook signal/i)).toBeInTheDocument();
    });

    test('shows using custom capital message when toggle is on', () => {
      renderWithTheme(
        <DCAConfigForm
          open={true}
          onClose={mockOnClose}
          onSubmit={mockOnSubmit}
          initialData={{
            ...mockInitialData,
            use_custom_capital: true,
            custom_capital_usd: 500,
          }}
          isEdit={true}
        />
      );

      expect(screen.getByText(/using custom capital from settings below/i)).toBeInTheDocument();
    });
  });
});
