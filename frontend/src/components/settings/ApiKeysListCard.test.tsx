import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { ThemeProvider } from '@mui/material/styles';
import ApiKeysListCard from './ApiKeysListCard';
import { darkTheme } from '../../theme/theme';

const renderWithTheme = (component: React.ReactElement) => {
  return render(
    <ThemeProvider theme={darkTheme}>{component}</ThemeProvider>
  );
};

describe('ApiKeysListCard', () => {
  const mockOnEdit = jest.fn();
  const mockOnDelete = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Empty State', () => {
    test('renders empty state when no exchanges configured', () => {
      renderWithTheme(
        <ApiKeysListCard
          configuredExchanges={[]}
          activeExchange=""
          onEdit={mockOnEdit}
          onDelete={mockOnDelete}
        />
      );

      expect(screen.getByText(/no exchanges configured yet/i)).toBeInTheDocument();
    });

    test('displays 0 exchange(s) configured in description', () => {
      renderWithTheme(
        <ApiKeysListCard
          configuredExchanges={[]}
          activeExchange=""
          onEdit={mockOnEdit}
          onDelete={mockOnDelete}
        />
      );

      expect(screen.getByText('0 exchange(s) configured')).toBeInTheDocument();
    });
  });

  describe('With Configured Exchanges', () => {
    test('renders list of configured exchanges', () => {
      renderWithTheme(
        <ApiKeysListCard
          configuredExchanges={['binance', 'bybit']}
          activeExchange="binance"
          onEdit={mockOnEdit}
          onDelete={mockOnDelete}
        />
      );

      expect(screen.getByText('binance')).toBeInTheDocument();
      expect(screen.getByText('bybit')).toBeInTheDocument();
    });

    test('displays correct exchange count in description', () => {
      renderWithTheme(
        <ApiKeysListCard
          configuredExchanges={['binance', 'bybit', 'kucoin']}
          activeExchange="binance"
          onEdit={mockOnEdit}
          onDelete={mockOnDelete}
        />
      );

      expect(screen.getByText('3 exchange(s) configured')).toBeInTheDocument();
    });

    test('shows Active chip for active exchange', () => {
      renderWithTheme(
        <ApiKeysListCard
          configuredExchanges={['binance', 'bybit']}
          activeExchange="binance"
          onEdit={mockOnEdit}
          onDelete={mockOnDelete}
        />
      );

      expect(screen.getByText('Active')).toBeInTheDocument();
    });

    test('does not show Active chip for inactive exchanges', () => {
      renderWithTheme(
        <ApiKeysListCard
          configuredExchanges={['binance']}
          activeExchange="bybit"
          onEdit={mockOnEdit}
          onDelete={mockOnDelete}
        />
      );

      expect(screen.queryByText('Active')).not.toBeInTheDocument();
    });
  });

  describe('Exchange Details', () => {
    test('shows Test chip when exchange is testnet', () => {
      renderWithTheme(
        <ApiKeysListCard
          configuredExchanges={['binance']}
          activeExchange="binance"
          exchangeDetails={{ binance: { testnet: true } }}
          onEdit={mockOnEdit}
          onDelete={mockOnDelete}
        />
      );

      expect(screen.getByText('Test')).toBeInTheDocument();
    });

    test('does not show Test chip when testnet is false', () => {
      renderWithTheme(
        <ApiKeysListCard
          configuredExchanges={['binance']}
          activeExchange="binance"
          exchangeDetails={{ binance: { testnet: false } }}
          onEdit={mockOnEdit}
          onDelete={mockOnDelete}
        />
      );

      expect(screen.queryByText('Test')).not.toBeInTheDocument();
    });

    test('displays account type when provided', () => {
      renderWithTheme(
        <ApiKeysListCard
          configuredExchanges={['binance']}
          activeExchange="binance"
          exchangeDetails={{ binance: { account_type: 'futures' } }}
          onEdit={mockOnEdit}
          onDelete={mockOnDelete}
        />
      );

      expect(screen.getByText('futures')).toBeInTheDocument();
    });

    test('handles missing exchange details gracefully', () => {
      renderWithTheme(
        <ApiKeysListCard
          configuredExchanges={['binance', 'bybit']}
          activeExchange="binance"
          exchangeDetails={{ binance: { testnet: true } }}
          onEdit={mockOnEdit}
          onDelete={mockOnDelete}
        />
      );

      // Should still render both exchanges
      expect(screen.getByText('binance')).toBeInTheDocument();
      expect(screen.getByText('bybit')).toBeInTheDocument();
    });
  });

  describe('Actions', () => {
    test('calls onEdit with exchange name when edit button clicked', () => {
      renderWithTheme(
        <ApiKeysListCard
          configuredExchanges={['binance', 'bybit']}
          activeExchange="binance"
          onEdit={mockOnEdit}
          onDelete={mockOnDelete}
        />
      );

      const editButtons = screen.getAllByRole('button', { name: /edit/i });
      fireEvent.click(editButtons[0]);

      expect(mockOnEdit).toHaveBeenCalledWith('binance');
    });

    test('calls onDelete with exchange name when delete button clicked', () => {
      renderWithTheme(
        <ApiKeysListCard
          configuredExchanges={['binance', 'bybit']}
          activeExchange="binance"
          onEdit={mockOnEdit}
          onDelete={mockOnDelete}
        />
      );

      const deleteButtons = screen.getAllByRole('button', { name: /delete/i });
      fireEvent.click(deleteButtons[1]);

      expect(mockOnDelete).toHaveBeenCalledWith('bybit');
    });

    test('renders edit and delete buttons for each exchange', () => {
      renderWithTheme(
        <ApiKeysListCard
          configuredExchanges={['binance', 'bybit', 'kucoin']}
          activeExchange="binance"
          onEdit={mockOnEdit}
          onDelete={mockOnDelete}
        />
      );

      const editButtons = screen.getAllByRole('button', { name: /edit/i });
      const deleteButtons = screen.getAllByRole('button', { name: /delete/i });

      expect(editButtons).toHaveLength(3);
      expect(deleteButtons).toHaveLength(3);
    });
  });

  describe('Card Structure', () => {
    test('renders API Keys title', () => {
      renderWithTheme(
        <ApiKeysListCard
          configuredExchanges={['binance']}
          activeExchange="binance"
          onEdit={mockOnEdit}
          onDelete={mockOnDelete}
        />
      );

      expect(screen.getByText('API Keys')).toBeInTheDocument();
    });
  });
});
