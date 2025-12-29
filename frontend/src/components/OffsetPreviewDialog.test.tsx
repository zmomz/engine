import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { ThemeProvider, createTheme } from '@mui/material';
import OffsetPreviewDialog, { OffsetPreviewData } from './OffsetPreviewDialog';

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

describe('OffsetPreviewDialog', () => {
  const mockOnClose = jest.fn();
  const mockOnConfirm = jest.fn();

  const validData: OffsetPreviewData = {
    loser: {
      id: 'pos-1',
      symbol: 'BTC/USDT',
      unrealized_pnl_percent: -5.25,
      unrealized_pnl_usd: -150.50,
      pyramid_count: 2,
      max_pyramids: 3,
      age_minutes: 45,
    },
    winners: [
      {
        symbol: 'ETH/USDT',
        profit_available: 200.00,
        amount_to_close: 150.50,
        partial: false,
      },
    ],
    required_offset_usd: 150.50,
    total_available_profit: 200.00,
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('when data is null', () => {
    it('returns null', () => {
      const { container } = renderWithTheme(
        <OffsetPreviewDialog
          open={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          data={null}
        />
      );
      expect(container.firstChild).toBeNull();
    });
  });

  describe('dialog structure', () => {
    it('renders dialog title', () => {
      renderWithTheme(
        <OffsetPreviewDialog
          open={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          data={validData}
        />
      );
      expect(screen.getByText('Offset Preview')).toBeInTheDocument();
    });

    it('renders losing position section', () => {
      renderWithTheme(
        <OffsetPreviewDialog
          open={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          data={validData}
        />
      );
      expect(screen.getByText('Losing Position')).toBeInTheDocument();
    });

    it('renders loser symbol', () => {
      renderWithTheme(
        <OffsetPreviewDialog
          open={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          data={validData}
        />
      );
      expect(screen.getByText('BTC/USDT')).toBeInTheDocument();
    });

    it('renders loser loss percentage', () => {
      renderWithTheme(
        <OffsetPreviewDialog
          open={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          data={validData}
        />
      );
      expect(screen.getByText('-5.25%')).toBeInTheDocument();
    });

    it('renders loser loss amount', () => {
      renderWithTheme(
        <OffsetPreviewDialog
          open={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          data={validData}
        />
      );
      // Multiple elements have this value, verify it's present
      expect(screen.getAllByText(/\$150\.50/).length).toBeGreaterThan(0);
    });

    it('renders loser age', () => {
      renderWithTheme(
        <OffsetPreviewDialog
          open={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          data={validData}
        />
      );
      expect(screen.getByText('45 min')).toBeInTheDocument();
    });

    it('renders loser pyramid count', () => {
      renderWithTheme(
        <OffsetPreviewDialog
          open={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          data={validData}
        />
      );
      expect(screen.getByText('2/3')).toBeInTheDocument();
    });
  });

  describe('offset plan section', () => {
    it('renders offset plan heading with count (singular)', () => {
      renderWithTheme(
        <OffsetPreviewDialog
          open={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          data={validData}
        />
      );
      expect(screen.getByText('Offset Plan (1 winner)')).toBeInTheDocument();
    });

    it('renders offset plan heading with count (plural)', () => {
      const dataWithMultipleWinners: OffsetPreviewData = {
        ...validData,
        winners: [
          { symbol: 'ETH/USDT', profit_available: 100, amount_to_close: 75, partial: false },
          { symbol: 'SOL/USDT', profit_available: 100, amount_to_close: 75.50, partial: true },
        ],
      };
      renderWithTheme(
        <OffsetPreviewDialog
          open={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          data={dataWithMultipleWinners}
        />
      );
      expect(screen.getByText('Offset Plan (2 winners)')).toBeInTheDocument();
    });

    it('renders winner symbols', () => {
      renderWithTheme(
        <OffsetPreviewDialog
          open={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          data={validData}
        />
      );
      expect(screen.getByText('ETH/USDT')).toBeInTheDocument();
    });

    it('renders winner amount to close', () => {
      renderWithTheme(
        <OffsetPreviewDialog
          open={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          data={validData}
        />
      );
      // Multiple elements display this value
      expect(screen.getAllByText(/\$150\.50/).length).toBeGreaterThan(0);
    });

    it('renders partial chip when winner is partial', () => {
      const dataWithPartial: OffsetPreviewData = {
        ...validData,
        winners: [
          { symbol: 'ETH/USDT', profit_available: 200, amount_to_close: 100, partial: true },
        ],
      };
      renderWithTheme(
        <OffsetPreviewDialog
          open={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          data={dataWithPartial}
        />
      );
      expect(screen.getByText('Partial')).toBeInTheDocument();
    });

    it('does not render partial chip when winner is not partial', () => {
      renderWithTheme(
        <OffsetPreviewDialog
          open={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          data={validData}
        />
      );
      expect(screen.queryByText('Partial')).not.toBeInTheDocument();
    });

    it('renders winner profit available', () => {
      renderWithTheme(
        <OffsetPreviewDialog
          open={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          data={validData}
        />
      );
      expect(screen.getByText('Available: $200.00')).toBeInTheDocument();
    });
  });

  describe('summary section', () => {
    it('renders required offset', () => {
      renderWithTheme(
        <OffsetPreviewDialog
          open={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          data={validData}
        />
      );
      expect(screen.getByText('Required Offset')).toBeInTheDocument();
    });

    it('renders available profit', () => {
      renderWithTheme(
        <OffsetPreviewDialog
          open={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          data={validData}
        />
      );
      expect(screen.getByText('Available Profit')).toBeInTheDocument();
    });

    it('renders net result', () => {
      renderWithTheme(
        <OffsetPreviewDialog
          open={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          data={validData}
        />
      );
      expect(screen.getByText('Net Result')).toBeInTheDocument();
    });

    it('shows positive net result', () => {
      renderWithTheme(
        <OffsetPreviewDialog
          open={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          data={validData}
        />
      );
      // Net is 200 - 150.50 = 49.50
      expect(screen.getByText('$49.50')).toBeInTheDocument();
    });

    it('shows negative net result when insufficient profit', () => {
      const insufficientData: OffsetPreviewData = {
        ...validData,
        total_available_profit: 100.00,
        required_offset_usd: 150.50,
      };
      renderWithTheme(
        <OffsetPreviewDialog
          open={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          data={insufficientData}
        />
      );
      // Net is 100 - 150.50 = -50.50
      expect(screen.getByText('$-50.50')).toBeInTheDocument();
    });
  });

  describe('alerts', () => {
    it('shows info alert when can execute', () => {
      renderWithTheme(
        <OffsetPreviewDialog
          open={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          data={validData}
        />
      );
      expect(screen.getByText('This offset will be executed immediately.')).toBeInTheDocument();
    });

    it('shows warning alert when cannot execute', () => {
      const insufficientData: OffsetPreviewData = {
        ...validData,
        total_available_profit: 100.00,
      };
      renderWithTheme(
        <OffsetPreviewDialog
          open={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          data={insufficientData}
        />
      );
      expect(screen.getByText('Insufficient profit to execute this offset. Additional winning positions needed.')).toBeInTheDocument();
    });
  });

  describe('buttons', () => {
    it('renders cancel button', () => {
      renderWithTheme(
        <OffsetPreviewDialog
          open={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          data={validData}
        />
      );
      expect(screen.getByRole('button', { name: 'Cancel' })).toBeInTheDocument();
    });

    it('calls onClose when cancel clicked', () => {
      renderWithTheme(
        <OffsetPreviewDialog
          open={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          data={validData}
        />
      );
      fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
      expect(mockOnClose).toHaveBeenCalled();
    });

    it('renders execute button', () => {
      renderWithTheme(
        <OffsetPreviewDialog
          open={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          data={validData}
        />
      );
      expect(screen.getByRole('button', { name: 'Execute Offset' })).toBeInTheDocument();
    });

    it('calls onConfirm when execute clicked', () => {
      renderWithTheme(
        <OffsetPreviewDialog
          open={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          data={validData}
        />
      );
      fireEvent.click(screen.getByRole('button', { name: 'Execute Offset' }));
      expect(mockOnConfirm).toHaveBeenCalled();
    });

    it('disables execute button when cannot execute', () => {
      const insufficientData: OffsetPreviewData = {
        ...validData,
        total_available_profit: 100.00,
      };
      renderWithTheme(
        <OffsetPreviewDialog
          open={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          data={insufficientData}
        />
      );
      expect(screen.getByRole('button', { name: 'Execute Offset' })).toBeDisabled();
    });

    it('disables execute button when loading', () => {
      renderWithTheme(
        <OffsetPreviewDialog
          open={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          data={validData}
          loading={true}
        />
      );
      expect(screen.getByRole('button', { name: 'Executing...' })).toBeDisabled();
    });

    it('shows loading text when loading', () => {
      renderWithTheme(
        <OffsetPreviewDialog
          open={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          data={validData}
          loading={true}
        />
      );
      expect(screen.getByRole('button', { name: 'Executing...' })).toBeInTheDocument();
    });
  });

  describe('dialog state', () => {
    it('does not render when closed', () => {
      renderWithTheme(
        <OffsetPreviewDialog
          open={false}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          data={validData}
        />
      );
      expect(screen.queryByText('Offset Preview')).not.toBeInTheDocument();
    });
  });
});
