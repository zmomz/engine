import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { ThemeProvider } from '@mui/material/styles';
import DCAConfigCard from './DCAConfigCard';
import { darkTheme } from '../../theme/theme';
import { DCAConfiguration } from '../../api/dcaConfig';

const renderWithTheme = (component: React.ReactElement) => {
  return render(
    <ThemeProvider theme={darkTheme}>{component}</ThemeProvider>
  );
};

const createMockConfig = (overrides: Partial<DCAConfiguration> = {}): DCAConfiguration => ({
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
  ...overrides,
});

describe('DCAConfigCard', () => {
  const mockOnEdit = jest.fn();
  const mockOnDelete = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Basic Rendering', () => {
    test('renders pair name', () => {
      const config = createMockConfig();
      renderWithTheme(
        <DCAConfigCard config={config} onEdit={mockOnEdit} onDelete={mockOnDelete} />
      );

      expect(screen.getByText('BTC/USDT')).toBeInTheDocument();
    });

    test('renders exchange name', () => {
      const config = createMockConfig();
      renderWithTheme(
        <DCAConfigCard config={config} onEdit={mockOnEdit} onDelete={mockOnDelete} />
      );

      expect(screen.getByText('binance')).toBeInTheDocument();
    });

    test('renders max pyramids', () => {
      const config = createMockConfig({ max_pyramids: 8 });
      renderWithTheme(
        <DCAConfigCard config={config} onEdit={mockOnEdit} onDelete={mockOnDelete} />
      );

      expect(screen.getByText('8')).toBeInTheDocument();
    });

    test('renders DCA levels count', () => {
      const config = createMockConfig();
      renderWithTheme(
        <DCAConfigCard config={config} onEdit={mockOnEdit} onDelete={mockOnDelete} />
      );

      expect(screen.getByText('2')).toBeInTheDocument();
    });

    test('renders timeframe chip', () => {
      const config = createMockConfig({ timeframe: 15 });
      renderWithTheme(
        <DCAConfigCard config={config} onEdit={mockOnEdit} onDelete={mockOnDelete} />
      );

      expect(screen.getByText('15m')).toBeInTheDocument();
    });
  });

  describe('Entry Order Type Display', () => {
    test('displays Limit for limit order type', () => {
      const config = createMockConfig({ entry_order_type: 'limit' });
      renderWithTheme(
        <DCAConfigCard config={config} onEdit={mockOnEdit} onDelete={mockOnDelete} />
      );

      expect(screen.getByText('Limit')).toBeInTheDocument();
    });

    test('displays Market for market order type', () => {
      const config = createMockConfig({ entry_order_type: 'market' });
      renderWithTheme(
        <DCAConfigCard config={config} onEdit={mockOnEdit} onDelete={mockOnDelete} />
      );

      expect(screen.getByText('Market')).toBeInTheDocument();
    });
  });

  describe('TP Mode Display', () => {
    test('displays Per Leg for per_leg mode', () => {
      const config = createMockConfig({ tp_mode: 'per_leg' });
      renderWithTheme(
        <DCAConfigCard config={config} onEdit={mockOnEdit} onDelete={mockOnDelete} />
      );

      expect(screen.getByText('Per Leg')).toBeInTheDocument();
    });

    test('displays Aggregate for aggregate mode', () => {
      const config = createMockConfig({ tp_mode: 'aggregate' });
      renderWithTheme(
        <DCAConfigCard config={config} onEdit={mockOnEdit} onDelete={mockOnDelete} />
      );

      expect(screen.getByText('Aggregate')).toBeInTheDocument();
    });

    test('displays Hybrid for hybrid mode', () => {
      const config = createMockConfig({ tp_mode: 'hybrid' });
      renderWithTheme(
        <DCAConfigCard config={config} onEdit={mockOnEdit} onDelete={mockOnDelete} />
      );

      expect(screen.getByText('Hybrid')).toBeInTheDocument();
    });

    test('displays Pyr Agg for pyramid_aggregate mode', () => {
      const config = createMockConfig({ tp_mode: 'pyramid_aggregate' });
      renderWithTheme(
        <DCAConfigCard config={config} onEdit={mockOnEdit} onDelete={mockOnDelete} />
      );

      expect(screen.getByText('Pyr Agg')).toBeInTheDocument();
    });

    test('displays raw value for unknown mode', () => {
      const config = createMockConfig({ tp_mode: 'custom_mode' as any });
      renderWithTheme(
        <DCAConfigCard config={config} onEdit={mockOnEdit} onDelete={mockOnDelete} />
      );

      expect(screen.getByText('custom_mode')).toBeInTheDocument();
    });
  });

  describe('Actions', () => {
    test('calls onEdit when edit button is clicked', () => {
      const config = createMockConfig();
      renderWithTheme(
        <DCAConfigCard config={config} onEdit={mockOnEdit} onDelete={mockOnDelete} />
      );

      const editButtons = screen.getAllByRole('button');
      const editButton = editButtons.find(btn => btn.querySelector('[data-testid="EditIcon"]'));
      fireEvent.click(editButton!);

      expect(mockOnEdit).toHaveBeenCalledWith(config);
    });

    test('calls onDelete when delete button is clicked', () => {
      const config = createMockConfig({ id: 'test-id-456' });
      renderWithTheme(
        <DCAConfigCard config={config} onEdit={mockOnEdit} onDelete={mockOnDelete} />
      );

      const deleteButtons = screen.getAllByRole('button');
      const deleteButton = deleteButtons.find(btn => btn.querySelector('[data-testid="DeleteIcon"]'));
      fireEvent.click(deleteButton!);

      expect(mockOnDelete).toHaveBeenCalledWith('test-id-456');
    });
  });

  describe('Expand/Collapse', () => {
    test('shows expand button initially', () => {
      const config = createMockConfig();
      renderWithTheme(
        <DCAConfigCard config={config} onEdit={mockOnEdit} onDelete={mockOnDelete} />
      );

      expect(screen.getByTestId('KeyboardArrowDownIcon')).toBeInTheDocument();
    });

    test('expands to show DCA levels when clicked', () => {
      const config = createMockConfig({
        dca_levels: [
          { gap_percent: 0, weight_percent: 40, tp_percent: 1.5 },
          { gap_percent: 1.5, weight_percent: 60, tp_percent: 2 },
        ],
      });
      renderWithTheme(
        <DCAConfigCard config={config} onEdit={mockOnEdit} onDelete={mockOnDelete} />
      );

      const expandButton = screen.getByTestId('KeyboardArrowDownIcon').parentElement;
      fireEvent.click(expandButton!);

      // After expansion, should see DCA Levels header in expanded section
      expect(screen.getAllByText('DCA Levels').length).toBeGreaterThan(0);
      expect(screen.getByText('#0: Gap 0%')).toBeInTheDocument();
      expect(screen.getByText('40% @ 1.5% TP')).toBeInTheDocument();
    });

    test('shows collapse button after expansion', () => {
      const config = createMockConfig();
      renderWithTheme(
        <DCAConfigCard config={config} onEdit={mockOnEdit} onDelete={mockOnDelete} />
      );

      const expandButton = screen.getByTestId('KeyboardArrowDownIcon').parentElement;
      fireEvent.click(expandButton!);

      expect(screen.getByTestId('KeyboardArrowUpIcon')).toBeInTheDocument();
    });

    test('collapses back when clicked again', () => {
      const config = createMockConfig({
        dca_levels: [
          { gap_percent: 0, weight_percent: 100, tp_percent: 2 },
        ],
      });
      renderWithTheme(
        <DCAConfigCard config={config} onEdit={mockOnEdit} onDelete={mockOnDelete} />
      );

      const expandButton = screen.getByTestId('KeyboardArrowDownIcon').parentElement;
      fireEvent.click(expandButton!);

      const collapseButton = screen.getByTestId('KeyboardArrowUpIcon').parentElement;
      fireEvent.click(collapseButton!);

      expect(screen.getByTestId('KeyboardArrowDownIcon')).toBeInTheDocument();
    });
  });

  describe('Expanded Details', () => {
    test('shows aggregate TP percent when set', () => {
      const config = createMockConfig({
        tp_mode: 'aggregate',
        tp_settings: { tp_aggregate_percent: 2.5 },
      });
      renderWithTheme(
        <DCAConfigCard config={config} onEdit={mockOnEdit} onDelete={mockOnDelete} />
      );

      const expandButton = screen.getByTestId('KeyboardArrowDownIcon').parentElement;
      fireEvent.click(expandButton!);

      expect(screen.getByText(/Aggregate TP: 2.5%/)).toBeInTheDocument();
    });

    test('shows pyramid TP percents for pyramid_aggregate mode', () => {
      const config = createMockConfig({
        tp_mode: 'pyramid_aggregate',
        tp_settings: {
          tp_aggregate_percent: 2,
          pyramid_tp_percents: { '1': 1.5, '2': 2.0 },
        },
      });
      renderWithTheme(
        <DCAConfigCard config={config} onEdit={mockOnEdit} onDelete={mockOnDelete} />
      );

      const expandButton = screen.getByTestId('KeyboardArrowDownIcon').parentElement;
      fireEvent.click(expandButton!);

      expect(screen.getByText(/Pyramid TPs:/)).toBeInTheDocument();
      expect(screen.getByText(/P1: 1.5%/)).toBeInTheDocument();
    });

    test('shows pyramid specific levels info', () => {
      const config = createMockConfig({
        pyramid_specific_levels: {
          '1': [{ gap_percent: 0.5, weight_percent: 100, tp_percent: 1 }],
          '3': [{ gap_percent: 1, weight_percent: 100, tp_percent: 2 }],
        },
      });
      renderWithTheme(
        <DCAConfigCard config={config} onEdit={mockOnEdit} onDelete={mockOnDelete} />
      );

      const expandButton = screen.getByTestId('KeyboardArrowDownIcon').parentElement;
      fireEvent.click(expandButton!);

      expect(screen.getByText(/Custom pyramids: 1, 3/)).toBeInTheDocument();
    });
  });

  describe('Edge Cases', () => {
    test('handles empty dca_levels', () => {
      const config = createMockConfig({ dca_levels: [] });
      renderWithTheme(
        <DCAConfigCard config={config} onEdit={mockOnEdit} onDelete={mockOnDelete} />
      );

      expect(screen.getByText('0')).toBeInTheDocument();
    });

    test('handles undefined dca_levels', () => {
      const config = createMockConfig({ dca_levels: undefined as any });
      renderWithTheme(
        <DCAConfigCard config={config} onEdit={mockOnEdit} onDelete={mockOnDelete} />
      );

      expect(screen.getByText('0')).toBeInTheDocument();
    });

    test('handles missing tp_settings', () => {
      const config = createMockConfig({ tp_settings: undefined as any });
      renderWithTheme(
        <DCAConfigCard config={config} onEdit={mockOnEdit} onDelete={mockOnDelete} />
      );

      // Should render without error
      expect(screen.getByText('BTC/USDT')).toBeInTheDocument();
    });

    test('does not show aggregate TP when value is 0', () => {
      const config = createMockConfig({
        tp_mode: 'aggregate',
        tp_settings: { tp_aggregate_percent: 0 },
      });
      renderWithTheme(
        <DCAConfigCard config={config} onEdit={mockOnEdit} onDelete={mockOnDelete} />
      );

      const expandButton = screen.getByTestId('KeyboardArrowDownIcon').parentElement;
      fireEvent.click(expandButton!);

      expect(screen.queryByText(/Aggregate TP:/)).not.toBeInTheDocument();
    });
  });
});
